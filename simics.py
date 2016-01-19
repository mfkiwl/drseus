from __future__ import print_function
from datetime import datetime
import os
from random import choice, randrange
from re import findall
from shutil import copyfile
from signal import SIGINT
import subprocess
import sys
from termcolor import colored
from threading import Thread
from time import sleep, time

from dut import dut
from error import DrSEUsError
import simics_config
from simics_targets import devices
from sql import sql
from targets import choose_register, choose_target


class simics:
    error_messages = ['Address not mapped', 'Illegal Instruction',
                      'Illegal instruction', 'Illegal memory mapping',
                      'Illegal Memory Mapping', 'Error setting attribute',
                      'dropping memop (peer attribute not set)',
                      'where nothing is mapped', 'Error']

    def __init__(self, campaign_data, result_data, options, rsakey):
        self.simics = None
        self.campaign_data = campaign_data
        self.result_data = result_data
        self.options = options
        self.rsakey = rsakey
        if campaign_data['architecture'] == 'p2020':
            self.board = 'p2020rdb'
        elif campaign_data['architecture'] == 'a9':
            self.board = 'a9x2'
        self.targets = devices[self.board]
        if options.command == 'inject' and options.selected_targets is not None:
            for target in options.selected_targets:
                if target not in self.targets:
                    raise Exception('invalid injection target: '+target)

        if options.command == 'new':
            self.__launch_simics()
        elif options.command == 'supervise':
            self.__launch_simics(
                'gold-checkpoints/'+str(self.campaign_data['id'])+'/' +
                str(self.campaign_data['num_checkpoints'])+'_merged')
            self.continue_dut()

    def __str__(self):
        string = 'Simics simulation of '+self.board
        return string

    def __launch_simics(self, checkpoint=None):

        def do_uboot():
            if self.campaign_data['use_aux']:
                def stop_aux_boot():
                    self.aux.read_until('autoboot: ')
                    self.aux.serial.write('\n')
                aux_process = Thread(target=stop_aux_boot)
                aux_process.start()
            self.dut.read_until('autoboot: ')
            self.dut.serial.write('\n')
            if self.campaign_data['use_aux']:
                aux_process.join()
            self.halt_dut()
            if self.board == 'p2020rdb':
                self.__command('DUT_p2020rdb.soc.phys_mem.load-file '
                               '$initrd_image $initrd_addr')
                if self.campaign_data['use_aux']:
                    self.__command('AUX_p2020rdb_1.soc.phys_mem.load-file '
                                   '$initrd_image $initrd_addr')
                self.continue_dut()
                self.dut.serial.write('setenv ethaddr 00:01:af:07:9b:8a\n'
                                      'setenv eth1addr 00:01:af:07:9b:8b\n'
                                      'setenv eth2addr 00:01:af:07:9b:8c\n'
                                      'setenv consoledev ttyS0\n'
                                      'setenv bootargs root=/dev/ram rw '
                                      'console=$consoledev,$baudrate\n'
                                      'bootm ef080000 10000000 ef040000\n')
                if self.campaign_data['use_aux']:
                    self.aux.serial.write('setenv ethaddr 00:01:af:07:9b:8d\n'
                                          'setenv eth1addr 00:01:af:07:9b:8e\n'
                                          'setenv eth2addr 00:01:af:07:9b:8f\n'
                                          'setenv consoledev ttyS0\n'
                                          'setenv bootargs root=/dev/ram rw '
                                          'console=$consoledev,$baudrate\n'
                                          'bootm ef080000 10000000 ef040000\n')
            elif self.board == 'a9x2':
                self.__command('DUT_a9x2.coretile.mpcore.phys_mem.load-file '
                               '$kernel_image $kernel_addr')
                self.__command('DUT_a9x2.coretile.mpcore.phys_mem.load-file '
                               '$initrd_image $initrd_addr')
                if self.campaign_data['use_aux']:
                    self.__command('AUX_a9x2_1.coretile.mpcore.phys_mem.'
                                   'load-file $kernel_image $kernel_addr')
                    self.__command('AUX_a9x2_1.coretile.mpcore.phys_mem.'
                                   'load-file $initrd_image $initrd_addr')
                self.continue_dut()
                self.dut.read_until('VExpress# ')
                self.dut.serial.write('setenv bootargs console=ttyAMA0 '
                                      'root=/dev/ram0 rw\n')
                self.dut.read_until('VExpress# ')
                self.dut.serial.write('bootm 0x40800000 0x70000000\n')
                # TODO: remove these after fixing command prompt
                self.dut.read_until('##')
                self.dut.read_until('##')
                if self.campaign_data['use_aux']:
                    self.aux.read_until('VExpress# ')
                    self.aux.serial.write('setenv bootargs console=ttyAMA0 '
                                          'root=/dev/ram0 rw\n')
                    self.aux.read_until('VExpress# ')
                    self.aux.serial.write('bootm 0x40800000 0x70000000\n')
                    # TODO: remove these after fixing command prompt
                    self.aux.read_until('##')
                    self.aux.read_until('##')

    # def __launch_simics(self, checkpoint=None):
        attempts = 10
        for attempt in xrange(attempts):
            self.simics = subprocess.Popen([os.getcwd()+'/simics-workspace/'
                                            'simics', '-no-win', '-no-gui',
                                            '-q'],
                                           cwd=os.getcwd()+'/simics-workspace',
                                           stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE)
            try:
                self.__read_until()
            except DrSEUsError:
                self.simics.kill()
                print(colored('error launching simics (attempt ' +
                              str(attempt+1)+'/'+str(attempts)+')', 'red'))
                if attempt < attempts-1:
                    sleep(30)
                elif attempt == attempts-1:
                    raise Exception('error launching simics, check your '
                                    'license connection')
            else:
                break
        if checkpoint is None:
            self.__command('$drseus=TRUE')
            buff = self.__command(
                'run-command-file simics-'+self.board+'/'+self.board+'-linux' +
                ('-ethernet' if self.campaign_data['use_aux'] else '') +
                '.simics')
        else:
            buff = self.__command('read-configuration '+checkpoint)
            buff += self.__command('connect-real-network-port-in ssh '
                                   'ethernet_switch0 target-ip=10.10.0.100')
            if self.campaign_data['use_aux']:
                buff += self.__command('connect-real-network-port-in ssh '
                                       'ethernet_switch0 target-ip=10.10.0.104')
        found_settings = 0
        if checkpoint is None:
            serial_ports = []
        else:
            serial_ports = [0, 0]
        ssh_ports = []
        for line in buff.split('\n'):
            if 'pseudo device opened: /dev/pts/' in line:
                if checkpoint is None:
                    serial_ports.append(line.split(':')[1].strip())
                else:
                    if 'AUX_' in line:
                        serial_ports[1] = line.split(':')[1].strip()
                    else:
                        serial_ports[0] = line.split(':')[1].strip()
                found_settings += 1
            elif 'Host TCP port' in line:
                ssh_ports.append(int(line.split('->')[0].split(' ')[-2]))
                found_settings += 1
            if not self.campaign_data['use_aux'] and found_settings == 2:
                break
            elif self.campaign_data['use_aux'] and found_settings == 4:
                break
        else:
            self.close()
            raise DrSEUsError('Error finding port or pseudoterminal')
        if self.board == 'p2020rdb':
            self.options.aux_prompt = self.options.dut_prompt = \
                'root@p2020rdb:~#'
        elif self.board == 'a9x2':
            self.options.aux_prompt = self.options.dut_prompt = '#'
        self.options.dut_serial_port = serial_ports[0]
        self.options.dut_baud_rate = 38400
        self.options.dut_scp_port = ssh_ports[0]
        self.dut = dut(self.campaign_data, self.result_data, self.options,
                       self.rsakey)
        if self.campaign_data['use_aux']:
            self.options.aux_serial_port = serial_ports[1]
            self.options.aux_baud_rate = ssh_ports[1]
            self.options.aux_scp_port = ssh_ports[1]
            self.aux = dut(self.campaign_data, self.result_data, self.options,
                           self.rsakey, aux=True)
        if checkpoint is None:
            self.continue_dut()
            do_uboot()
            if self.campaign_data['use_aux']:
                aux_process = Thread(
                    target=self.aux.do_login,
                    kwargs={'ip_address': '10.10.0.104',
                            'change_prompt': (self.board == 'a9x2'),
                            'simics': True})
                aux_process.start()
            self.dut.do_login(ip_address='10.10.0.100',
                              change_prompt=(self.board == 'a9x2'),
                              simics=True)
            if self.campaign_data['use_aux']:
                aux_process.join()
        else:
            self.dut.ip_address = '127.0.0.1'
            if self.board == 'a9x2':
                self.dut.prompt = 'DrSEUs# '
            if self.campaign_data['use_aux']:
                self.aux.ip_address = '127.0.0.1'
                if self.board == 'a9x2':
                    self.aux.prompt = 'DrSEUs# '

    def launch_simics_gui(self, checkpoint):
        dut_board = 'DUT_'+self.board
        if self.board == 'p2020rdb':
            serial_port = 'serial[0]'
        elif self.board == 'a9x2':
            serial_port = 'serial0'
        simics_commands = ('read-configuration '+checkpoint+';'
                           'new-text-console-comp text_console0;'
                           'disconnect '+dut_board+'.console0.serial'
                           ' '+dut_board+'.'+serial_port+';'
                           'connect text_console0.serial'
                           ' '+dut_board+'.'+serial_port+';'
                           'connect-real-network-port-in ssh '
                           'ethernet_switch0 target-ip=10.10.0.100;')
        if self.campaign_data['use_aux']:
            aux_board = 'AUX_'+self.board+'_1'
            simics_commands += ('new-text-console-comp text_console1;'
                                'disconnect '+aux_board+'.console0.serial'
                                ' '+aux_board+'.'+serial_port+';'
                                'connect text_console1.serial'
                                ' '+aux_board+'.'+serial_port+';'
                                'connect-real-network-port-in ssh '
                                'ethernet_switch0 target-ip=10.10.0.104;')
        os.system('cd simics-workspace; '
                  './simics-gui -e \"'+simics_commands+'\"')

    def close(self):

        def read_worker():
            try:
                self.read_until()
            except:
                pass

    # def close(self):
        try:
            self.dut.close()
            if self.campaign_data['use_aux']:
                self.aux.close()
        except AttributeError:
            pass
        if self.simics:
            self.simics.send_signal(SIGINT)
            try:
                self.simics.stdin.write('quit\n')
            except IOError:
                pass
            read_thread = Thread(target=read_worker)
            read_thread.start()
            read_thread.join(timeout=5)  # must be shorter than timeout in read
            if read_thread.is_alive():
                self.simics.kill()
                if self.options.command == 'new':
                    self.campaign_data['debugger_output'] += \
                        '\nkilled unresponsive simics process\n'
                else:
                    self.result_data['debugger_output'] += \
                        '\nkilled unresponsive simics process\n'
                if self.options.debug:
                    print(colored('killed unresponsive simics process',
                                  'yellow'))
            else:
                if self.options.command == 'new':
                    self.campaign_data['debugger_output'] += 'quit\n'
                else:
                    self.result_data['debugger_output'] += 'quit\n'
                if self.options.debug:
                    print(colored('quit', 'yellow'))
                self.simics.wait()
        self.simics = None

    def halt_dut(self):
        self.simics.send_signal(SIGINT)
        self.__read_until()
        return True

    def continue_dut(self):
        self.simics.stdin.write('run\n')
        if self.options.command == 'new':
            self.campaign_data['debugger_output'] += 'run\n'
        else:
            self.result_data['debugger_output'] += 'run\n'
        if self.options.debug:
            print(colored('run', 'yellow'))

    def __read_until(self, string=None):

        def read_char():
            self.char = None

            def read_char_worker():
                if self.simics:
                    self.char = \
                        self.simics.stdout.read(1).decode('utf-8', 'replace')

            read_thread = Thread(target=read_char_worker)
            read_thread.start()
            read_thread.join(timeout=30)  # must be longer than timeout in close
            if read_thread.is_alive():
                raise DrSEUsError('Timeout reading from simics')
            return self.char

    # def __read_until(self, string=None):
        if string is None:
            string = 'simics> '
        buff = ''
        while True:
            char = read_char()
            if not char:
                break
            if self.options.command == 'new':
                self.campaign_data['debugger_output'] += char
            else:
                self.result_data['debugger_output'] += char
            if self.options.debug:
                print(colored(char, 'yellow'), end='')
                sys.stdout.flush()
            buff += char
            if buff[-len(string):] == string:
                break
        if not self.options.command == 'supervise':
            with sql() as db:
                if self.options.command == 'new':
                    db.update_dict('campaign', self.campaign_data)
                else:
                    db.update_dict('result', self.result_data)
        for message in self.error_messages:
            if message in buff:
                raise DrSEUsError(message)
        return buff

    def __command(self, command):
        self.simics.stdin.write(command+'\n')
        if self.options.command == 'new':
            self.campaign_data['debugger_output'] += command+'\n'
        else:
            self.result_data['debugger_output'] += command+'\n'
        if self.options.debug:
            print(colored(command, 'yellow'))
        return self.__read_until()

    def time_application(self):

        def create_checkpoints():
            os.makedirs('simics-workspace/gold-checkpoints/' +
                        str(self.campaign_data['id']))
            self.campaign_data['cycles_between'] = \
                self.campaign_data['num_cycles'] / self.options.checkpoints
            self.halt_dut()
            if self.campaign_data['use_aux']:
                    aux_process = Thread(
                        target=self.aux.command,
                        args=('./'+self.campaign_data['aux_command'], ))
                    aux_process.start()
            self.dut.serial.write('./'+self.campaign_data['command']+'\n')
            read_thread = Thread(target=self.dut.read_until)
            read_thread.start()
            checkpoint = 0
            while True:
                checkpoint += 1
                self.__command('run-cycles ' +
                               str(self.campaign_data['cycles_between']))
                self.campaign_data['dut_output'] += ('***drseus_checkpoint: ' +
                                                     str(checkpoint)+'***\n')
                incremental_checkpoint = ('gold-checkpoints/' +
                                          str(self.campaign_data['id'])+'/' +
                                          str(checkpoint))
                self.__command('write-configuration '+incremental_checkpoint)
                if not read_thread.is_alive() or \
                    (self.campaign_data['use_aux'] and
                        self.campaign_data['kill_dut'] and
                        not aux_process.is_alive()):
                    merged_checkpoint = incremental_checkpoint+'_merged'
                    self.__command('!bin/checkpoint-merge ' +
                                   incremental_checkpoint+' '+merged_checkpoint)
                    break
            self.campaign_data['num_checkpoints'] = checkpoint
            self.continue_dut()
            if self.campaign_data['use_aux']:
                aux_process.join()
            if self.campaign_data['kill_dut']:
                self.dut.serial.write('\x03')
            read_thread.join()

    # def time_application(self):
        self.halt_dut()
        time_data = self.__command('print-time').split('\n')[-2].split()
        start_cycles = int(time_data[2])
        start_sim_time = float(time_data[3])
        start_time = time()
        self.continue_dut()
        for i in xrange(self.options.iterations):
            if self.campaign_data['use_aux']:
                aux_process = Thread(
                    target=self.aux.command,
                    args=('./'+self.campaign_data['aux_command'], ))
                aux_process.start()
            self.dut.serial.write(str('./'+self.campaign_data['command']+'\n'))
            if self.campaign_data['use_aux']:
                aux_process.join()
            if self.campaign_data['kill_dut']:
                self.dut.serial.write('\x03')
            self.dut.read_until()
        self.halt_dut()
        end_time = time()
        time_data = self.__command('print-time').split('\n')[-2].split()
        end_cycles = int(time_data[2])
        end_sim_time = float(time_data[3])
        self.continue_dut()
        self.campaign_data['exec_time'] = \
            (end_time - start_time) / self.options.iterations
        self.campaign_data['num_cycles'] = \
            int((end_cycles - start_cycles) / self.options.iterations)
        self.campaign_data['sim_time'] = \
            (end_sim_time - start_sim_time) / self.options.iterations
        create_checkpoints()

    def inject_faults(self):

        def persistent_faults():
            with sql(row_factory='row') as db:
                db.cursor.execute('SELECT config_object,register,'
                                  'register_index,injected_value '
                                  'FROM log_injection WHERE result_id=?',
                                  (self.result_data['id'],))
                injections = db.cursor.fetchall()
                db.cursor.execute('SELECT * FROM log_simics_register_diff '
                                  'WHERE result_id=?',
                                  (self.result_data['id'],))
                register_diffs = db.cursor.fetchall()
                db.cursor.execute('SELECT COUNT(*) FROM log_simics_memory_diff '
                                  'WHERE result_id=?',
                                  (self.result_data['id'],))
                memory_diffs = db.cursor.fetchone()[0]
            if memory_diffs > 0:
                return False
            for register_diff in register_diffs:
                for injection in injections:
                    if injection['register_index']:
                        injected_register = (injection['register']+':' +
                                             injection['register_index'])
                    else:
                        injected_register = injection['register']
                    if register_diff['config_object'] == \
                        injection['config_object'] and \
                            register_diff['register'] == injected_register:
                        if (int(register_diff['monitored_value'], base=0) ==
                                int(injection['injected_value'], base=0)):
                            break
                else:
                    return False
            else:
                return True

    # def inject_faults(self):
        checkpoint_nums = range(1, self.campaign_data['num_checkpoints'])
        checkpoints_to_inject = []
        for i in xrange(self.options.injections):
            checkpoint_num = choice(checkpoint_nums)
            checkpoint_nums.remove(checkpoint_num)
            checkpoints_to_inject.append(checkpoint_num)
        checkpoints_to_inject = sorted(checkpoints_to_inject)
        latent_faults = 0
        for injection_number in xrange(1, len(checkpoints_to_inject)+1):
            checkpoint_number = checkpoints_to_inject[injection_number-1]
            injected_checkpoint = self.__inject_checkpoint(injection_number,
                                                           checkpoint_number)
            self.__launch_simics(injected_checkpoint)
            injections_remaining = (injection_number <
                                    len(checkpoints_to_inject))
            if injections_remaining:
                next_checkpoint = checkpoints_to_inject[injection_number]
            else:
                next_checkpoint = self.campaign_data['num_checkpoints']
            errors = self.__compare_checkpoints(checkpoint_number,
                                                next_checkpoint)
            if errors > latent_faults:
                latent_faults = errors
            if injections_remaining:
                self.close()
        return latent_faults, (latent_faults and persistent_faults())

    def regenerate_checkpoints(self, injection_data):
        self.result_data['id'] = self.options.result_id
        for i in xrange(len(injection_data)):
            injected_checkpoint = self.__inject_checkpoint(
                injection_data[i]['injection_number'],
                injection_data[i]['checkpoint_number'], injection_data[i])
            if i < len(injection_data) - 1:
                self.__launch_simics(checkpoint=injected_checkpoint)
                for j in xrange(injection_data[i]['checkpoint_number'],
                                injection_data[i+1]['checkpoint_number']):
                    self.__command('run-cycles ' +
                                   str(self.campaign_data['cycles_between']))
                self.__command('write-configuration injected-checkpoints/' +
                               str(self.campaign_data['id'])+'/' +
                               str(self.options.result_id)+'/' +
                               str(injection_data[i+1]['checkpoint_number']))
                self.close()
        return injected_checkpoint

    def __inject_checkpoint(self, injection_number, checkpoint_number,
                            previous_injection_data=None):
        """
        Create a new injected checkpoint (only performing injection on the
        selected_targets if provided) and return the path of the injected
        checkpoint.
        """

        def inject_register(injected_checkpoint, register, target):
            """
            Creates config file for injected_checkpoint with an injected value
            for the register of the target in the gold_checkpoint and return the
            injection information.
            """

            def flip_bit(value_to_inject, num_bits_to_inject, bit_to_inject):
                """
                Flip the bit_to_inject of the binary representation of
                value_to_inject and return the new value.
                """
                if bit_to_inject >= num_bits_to_inject or bit_to_inject < 0:
                    raise Exception('simics.py:flip_bit():'
                                    ' invalid bit_to_inject: ' +
                                    str(bit_to_inject) +
                                    ' for num_bits_to_inject: ' +
                                    str(num_bits_to_inject))
                value_to_inject = int(value_to_inject, base=0)
                binary_list = list(
                    str(bin(value_to_inject))[2:].zfill(num_bits_to_inject))
                binary_list[num_bits_to_inject-1-bit_to_inject] = (
                    '1'
                    if binary_list[num_bits_to_inject-1-bit_to_inject] == '0'
                    else '0')
                injected_value = int(''.join(binary_list), 2)
                injected_value = hex(injected_value).rstrip('L')
                return injected_value

        # def inject_register(injected_checkpoint, register, target):
            if previous_injection_data is None:
                # create injection_data
                injection_data = {}
                injection_data['register'] = register
                if ':' in target:
                    target_index = target.split(':')[1]
                    target = target.split(':')[0]
                    config_object = ('DUT_'+self.board +
                                     self.targets[target]['OBJECT'] +
                                     '['+target_index+']')
                else:
                    target_index = None
                    config_object = \
                        'DUT_'+self.board+self.targets[target]['OBJECT']
                injection_data['target_index'] = target_index
                injection_data['target'] = target
                injection_data['config_object'] = config_object
                if 'count' in self.targets[target]['registers'][register]:
                    register_index = []
                    for dimension in (self.targets[target]['registers']
                                                  [register]['count']):
                        index = randrange(dimension)
                        register_index.append(index)
                else:
                    register_index = None
                # choose bit_to_inject and TLB field_to_inject
                if ('is_tlb' in self.targets[target]['registers'][register] and
                        self.targets[target]['registers'][register]['is_tlb']):
                    fields = \
                        self.targets[target]['registers'][register]['fields']
                    field_to_inject = None
                    fields_list = []
                    total_bits = 0
                    for field in fields:
                        bits = fields[field]['bits']
                        fields_list.append((field, bits))
                        total_bits += bits
                    random_bit = randrange(total_bits)
                    bit_sum = 0
                    for field in fields_list:
                        bit_sum += field[1]
                        if random_bit < bit_sum:
                            field_to_inject = field[0]
                            break
                    else:
                        raise Exception('simics.py:inject_register(): '
                                        'Error choosing TLB field to inject')
                    injection_data['field'] = field_to_inject
                    if 'split' in fields[field_to_inject] and \
                            fields[field_to_inject]['split']:
                        total_bits = (fields[field_to_inject]['bits_h'] +
                                      fields[field_to_inject]['bits_l'])
                        random_bit = randrange(total_bits)
                        if random_bit < fields[field_to_inject]['bits_l']:
                            register_index[-1] = \
                                fields[field_to_inject]['index_l']
                            start_bit_index = \
                                fields[field_to_inject]['bit_indicies_l'][0]
                            end_bit_index = \
                                fields[field_to_inject]['bit_indicies_l'][1]
                        else:
                            register_index[-1] = \
                                fields[field_to_inject]['index_h']
                            start_bit_index = \
                                fields[field_to_inject]['bit_indicies_h'][0]
                            end_bit_index = \
                                fields[field_to_inject]['bit_indicies_h'][1]
                    else:
                        register_index[-1] = fields[field_to_inject]['index']
                        start_bit_index = \
                            fields[field_to_inject]['bit_indicies'][0]
                        end_bit_index = \
                            fields[field_to_inject]['bit_indicies'][1]
                    num_bits_to_inject = 32
                    bit_to_inject = randrange(start_bit_index, end_bit_index+1)
                else:
                    if 'bits' in self.targets[target]['registers'][register]:
                        num_bits_to_inject = \
                            self.targets[target]['registers'][register]['bits']
                    else:
                        num_bits_to_inject = 32
                    bit_to_inject = randrange(num_bits_to_inject)
                    if 'adjust_bit' in \
                            self.targets[target]['registers'][register]:
                        bit_to_inject = (self.targets[target]['registers']
                                                     [register]['adjust_bit']
                                                     [bit_to_inject])
                    if 'actualBits' in \
                            self.targets[target]['registers'][register]:
                        num_bits_to_inject = \
                            (self.targets[target]['registers']
                                         [register]['actualBits'])
                    if 'fields' in self.targets[target]['registers'][register]:
                        for field_name, field_bounds in \
                            (self.targets[target]['registers']
                                         [register]['fields'].iteritems()):
                            if bit_to_inject in range(field_bounds[0],
                                                      field_bounds[1]+1):
                                field_to_inject = field_name
                                break
                        else:
                            raise Exception('checkpoints.py:inject_register(): '
                                            'Error finding register field name '
                                            'for bit '+str(bit_to_inject) +
                                            ' in register '+register)
                        injection_data['field'] = field_to_inject
                    else:
                        injection_data['field'] = None
                injection_data['bit'] = bit_to_inject

                if register_index is not None:
                    injection_data['register_index'] = ''
                    for index in register_index:
                        injection_data['register_index'] += str(index)+':'
                    injection_data['register_index'] = \
                        injection_data['register_index'][:-1]
                else:
                    injection_data['register_index'] = None
            else:
                # use previous injection data
                config_object = previous_injection_data['config_object']
                register = previous_injection_data['register']
                register_index = previous_injection_data['register_index']
                if register_index is not None:
                    register_index = [int(index) for index
                                      in register_index.split(':')]
                injection_data = {}
                injected_value = previous_injection_data['injected_value']
            # perform checkpoint injection
            config = simics_config.read_configuration(injected_checkpoint)
            gold_value = simics_config.get_attr(config, config_object, register)
            if register_index is None:
                if previous_injection_data is None:
                    injected_value = flip_bit(gold_value, num_bits_to_inject,
                                              bit_to_inject)
                simics_config.set_attr(config, config_object, register,
                                       injected_value)
            else:
                register_list_ = register_list = gold_value
                if previous_injection_data is None:
                    for index in register_index:
                        gold_value = gold_value[index]
                    injected_value = flip_bit(
                        gold_value, num_bits_to_inject, bit_to_inject)
                for index in xrange(len(register_index)-1):
                    register_list_ = register_list_[register_index[index]]
                register_list_[register_index[-1]] = injected_value
                simics_config.set_attr(config, config_object, register,
                                       register_list)
            simics_config.write_configuration(config, injected_checkpoint,
                                              False)
            injection_data['gold_value'] = gold_value
            injection_data['injected_value'] = injected_value
            return injection_data

    # def __inject_checkpoint(self, injection_number, checkpoint_number,
    #                         previous_injection_data=None):
        if injection_number == 1:
            gold_checkpoint = ('simics-workspace/gold-checkpoints/' +
                               str(self.campaign_data['id'])+'/' +
                               str(checkpoint_number))
        else:
            gold_checkpoint = ('simics-workspace/injected-checkpoints/' +
                               str(self.campaign_data['id'])+'/' +
                               str(self.result_data['id'])+'/' +
                               str(checkpoint_number))
        injected_checkpoint = ('simics-workspace/injected-checkpoints/' +
                               str(self.campaign_data['id'])+'/' +
                               str(self.result_data['id'])+'/' +
                               str(checkpoint_number)+'_injected')
        os.makedirs(injected_checkpoint)
        # copy gold checkpoint files
        checkpoint_files = os.listdir(gold_checkpoint)
        for checkpoint_file in checkpoint_files:
            copyfile(gold_checkpoint+'/'+checkpoint_file,
                     injected_checkpoint+'/'+checkpoint_file)
        if previous_injection_data is None:
            # choose injection target
            target = choose_target(self.options.selected_targets, self.targets)
            register = choose_register(target, self.targets)
            injection_data = {'result_id': self.result_data['id'],
                              'injection_number': injection_number,
                              'checkpoint_number': checkpoint_number,
                              'register': register,
                              'target': target,
                              'timestamp': datetime.now()}
            try:
                # perform fault injection
                injection_data.update(inject_register(injected_checkpoint,
                                                      register, target))
            except Exception as error:
                injection_data['success'] = False
                with sql() as db:
                    db.insert_dict('injection', injection_data)
                print(error)
                raise DrSEUsError('Error injecting fault')
            else:
                injection_data['success'] = True
            # log injection data
            with sql() as db:
                db.insert_dict('injection', injection_data)
            if self.options.debug:
                print(colored('result id: '+str(self.result_data['id']),
                              'magenta'))
                print(colored('injection number: '+str(injection_number),
                              'magenta'))
                print(colored('checkpoint number: '+str(checkpoint_number),
                              'magenta'))
                print(colored('target: '+injection_data['target'], 'magenta'))
                print(colored('register: '+injection_data['register'],
                              'magenta'))
                print(colored('gold value: '+injection_data['gold_value'],
                              'magenta'))
                print(colored('injected value: ' +
                              injection_data['injected_value'], 'magenta'))
        else:
            inject_register(injected_checkpoint, None, None)
        return injected_checkpoint.replace('simics-workspace/', '')

    def __compare_checkpoints(self, checkpoint_number, last_checkpoint):

        def compare_registers(checkpoint_number, gold_checkpoint,
                              monitored_checkpoint):
            """
            Compares the register values of the checkpoint_number for iteration
            to the gold_checkpoint and adds the differences to the database.
            """

            def get_registers(checkpoint):
                """
                Retrieves all the register values of the targets specified in
                simics_targets.py for the specified checkpoint and returns a
                dictionary with all the values.
                """
                config = simics_config.read_configuration(checkpoint)
                registers = {}
                for target in self.targets:
                    if target != 'TLB':
                        if 'count' in self.targets[target]:
                            count = self.targets[target]['count']
                        else:
                            count = 1
                        for target_index in xrange(count):
                            config_object = \
                                'DUT_'+self.board+self.targets[target]['OBJECT']
                            if count > 1:
                                config_object += '['+str(target_index)+']'
                            if target == 'GPR':
                                target_key = config_object + ':gprs'
                            else:
                                target_key = config_object
                            registers[target_key] = {}
                            for register in self.targets[target]['registers']:
                                registers[target_key][register] = \
                                    simics_config.get_attr(
                                        config, config_object, register)
                return registers

            # watch out! we're gonna use recursion
            # keep your arms and legs inside the stack frame at all times
            def log_diffs(db, config_object, register, gold_value,
                          monitored_value):
                if isinstance(gold_value, list):
                    for index in xrange(len(gold_value)):
                        log_diffs(db, config_object, register+':'+str(index),
                                  gold_value[index], monitored_value[index])
                else:
                    if int(monitored_value, base=0) != int(gold_value, base=0):
                        register_diff_data = {
                            'result_id': self.result_data['id'],
                            'checkpoint_number': checkpoint_number,
                            'config_object': config_object,
                            'register': register,
                            'gold_value': gold_value,
                            'monitored_value': monitored_value}
                        db.insert_dict('simics_register_diff',
                                       register_diff_data)

        # def compare_registers(checkpoint_number, gold_checkpoint,
        #                       monitored_checkpoint):
            gold_registers = get_registers(gold_checkpoint)
            monitored_registers = get_registers(monitored_checkpoint)
            with sql() as db:
                for config_object in gold_registers:
                    for register in gold_registers[config_object]:
                        log_diffs(db, config_object, register,
                                  gold_registers[config_object][register],
                                  monitored_registers[config_object][register])
                db.cursor.execute('SELECT COUNT(*) FROM '
                                  'log_simics_register_diff WHERE result_id=?',
                                  (self.result_data['id'],))
                diffs = db.cursor.fetchone()[0]
            return diffs

        def compare_memory(checkpoint_number, gold_checkpoint,
                           monitored_checkpoint, extract_blocks=False):
            """
            Compare the memory contents of gold_checkpoint with
            monitored_checkpoint and return the list of blocks that do not
            match. If extract_blocks is true then extract any blocks that do not
            match to incremental_checkpoint/memory-blocks/.
            """

            def parse_content_map(content_map, block_size):
                """
                Parse a content_map created by the Simics craff utility and
                returns a list of the addresses of the image that contain data.
                """
                with open(content_map, 'r') as content_map_file:
                    diff_addresses = []
                    for line in content_map_file:
                        if 'empty' not in line:
                            line = line.split()
                            base_address = int(line[0], 16)
                            offsets = [index for index, value
                                       in enumerate(line[1]) if value == 'D']
                            for offset in offsets:
                                diff_addresses.append(base_address +
                                                      offset*block_size)
                return diff_addresses

            def extract_diff_blocks(gold_ram, monitored_ram,
                                    incremental_checkpoint, addresses,
                                    block_size):
                """
                Extract all of the blocks of size block_size specified in
                addresses of both the gold_ram image and the monitored_ram
                image.
                """
                if len(addresses) > 0:
                    os.mkdir(incremental_checkpoint+'/memory-blocks')
                    for address in addresses:
                        gold_block = (incremental_checkpoint+'/memory-blocks/' +
                                      hex(address)+'_gold.raw')
                        monitored_block = (incremental_checkpoint +
                                           '/memory-blocks/'+hex(address) +
                                           '_monitored.raw')
                        os.system('simics-workspace/bin/craff '+gold_ram +
                                  ' --extract='+hex(address) +
                                  ' --extract-block-size='+str(block_size) +
                                  ' --output='+gold_block)
                        os.system('simics-workspace/bin/craff '+monitored_ram +
                                  ' --extract='+hex(address) +
                                  ' --extract-block-size='+str(block_size) +
                                  ' --output='+monitored_block)

        # def compare_memory(checkpoint_number, gold_checkpoint,
        #                    monitored_checkpoint, extract_blocks=False):
            if self.board == 'p2020rdb':
                gold_rams = [gold_checkpoint+'/DUT_'+self.board +
                             '.soc.ram_image['+str(index)+'].craff'
                             for index in xrange(1)]
                monitored_rams = [monitored_checkpoint+'/DUT_'+self.board +
                                  '.soc.ram_image['+str(index)+'].craff'
                                  for index in xrange(1)]
            elif self.board == 'a9x2':
                gold_rams = [gold_checkpoint+'/DUT_'+self.board +
                             '.coretile.ddr_image['+str(index)+'].craff'
                             for index in xrange(2)]
                monitored_rams = [monitored_checkpoint+'/DUT_'+self.board +
                                  '.coretile.ddr_image['+str(index)+'].craff'
                                  for index in xrange(2)]
            ram_diffs = [ram+'.diff' for ram in monitored_rams]
            diff_content_maps = [diff+'.content_map' for diff in ram_diffs]
            diffs = 0
            memory_diff_data = {'result_id': self.result_data['id'],
                                'checkpoint_number': checkpoint_number}
            with sql() as db:
                for (memory_diff_data['image_index'], gold_ram, monitored_ram,
                     ram_diff, diff_content_map) in zip(
                        range(len(monitored_rams)), gold_rams, monitored_rams,
                        ram_diffs, diff_content_maps):
                    os.system('simics-workspace/bin/craff --diff '+gold_ram +
                              ' '+monitored_ram+' --output='+ram_diff)
                    os.system('simics-workspace/bin/craff --content-map ' +
                              ram_diff+' --output='+diff_content_map)
                    craff_output = subprocess.check_output(
                        'simics-workspace/bin/craff --info '+ram_diff,
                        shell=True)
                    block_size = int(findall(r'\d+',
                                             craff_output.split('\n')[2])[1])
                    changed_blocks = parse_content_map(diff_content_map,
                                                       block_size)
                    diffs += len(changed_blocks)
                    if extract_blocks:
                        extract_diff_blocks(gold_ram, monitored_ram,
                                            monitored_checkpoint,
                                            changed_blocks, block_size)
                    for block in changed_blocks:
                        memory_diff_data['block'] = hex(block)
                        db.insert_dict('simics_memory_diff', memory_diff_data)
            return diffs

    # def __compare_checkpoints(self, checkpoint_number, last_checkpoint):
        reg_errors = 0
        mem_errors = 0
        for checkpoint_number in xrange(checkpoint_number + 1,
                                        last_checkpoint + 1):
            self.__command('run-cycles ' +
                           str(self.campaign_data['cycles_between']))
            incremental_checkpoint = (
                'injected-checkpoints/'+str(self.campaign_data['id'])+'/' +
                str(self.result_data['id'])+'/'+str(checkpoint_number))
            monitor = self.options.compare_all or \
                checkpoint_number == self.campaign_data['num_checkpoints']
            if monitor or checkpoint_number == last_checkpoint:
                self.__command('write-configuration '+incremental_checkpoint)
            if monitor:
                monitored_checkpoint = incremental_checkpoint+'_merged'
                self.__command('!bin/checkpoint-merge '+incremental_checkpoint +
                               ' '+monitored_checkpoint)
                gold_incremental_checkpoint = ('gold-checkpoints/' +
                                               str(self.campaign_data['id']) +
                                               '/'+str(checkpoint_number))
                gold_checkpoint = ('gold-checkpoints/' +
                                   str(self.campaign_data['id'])+'/' +
                                   str(checkpoint_number)+'_merged')
                if not os.path.exists('simics-workspace/'+gold_checkpoint):
                    self.__command('!bin/checkpoint-merge ' +
                                   gold_incremental_checkpoint+' ' +
                                   gold_checkpoint)
                gold_checkpoint = 'simics-workspace/'+gold_checkpoint
                monitored_checkpoint = 'simics-workspace/'+monitored_checkpoint
                errors = compare_registers(
                    checkpoint_number, gold_checkpoint, monitored_checkpoint)
                if errors > reg_errors:
                    reg_errors = errors
                errors = compare_memory(
                    checkpoint_number, gold_checkpoint, monitored_checkpoint)
                if errors > reg_errors:
                    mem_errors = errors
        return reg_errors + mem_errors
