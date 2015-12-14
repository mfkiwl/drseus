from __future__ import print_function
from datetime import datetime
from difflib import SequenceMatcher
import os
from paramiko import RSAKey
import random
import shutil
import sqlite3
import subprocess
from termcolor import colored
from threading import Thread
from time import sleep

from bdi import bdi_p2020, bdi_arm
from error import DrSEUsError
from openocd import openocd
from simics import simics
from sql import insert_dict, update_dict


class fault_injector:
    def __init__(self, campaign_number, dut_serial_port, aux_serial_port,
                 dut_prompt, aux_prompt, debugger_ip_address, architecture,
                 use_aux, debug, use_simics, timeout):
        self.campaign_number = campaign_number
        self.use_simics = use_simics
        self.use_aux = use_aux
        self.debug = debug
        if os.path.exists('campaign-data/'+str(campaign_number)+'/private.key'):
            self.rsakey = RSAKey.from_private_key_file('campaign-data/' +
                                                       str(campaign_number) +
                                                       '/private.key')
        else:
            self.rsakey = RSAKey.generate(1024)
            self.rsakey.write_private_key_file('campaign-data/' +
                                               str(campaign_number) +
                                               '/private.key')
        if self.use_simics:
            self.debugger = simics(campaign_number, architecture, self.rsakey,
                                   use_aux, debug, timeout)
        else:
            if architecture == 'p2020':
                self.debugger = bdi_p2020(debugger_ip_address, self.rsakey,
                                          dut_serial_port, aux_serial_port,
                                          use_aux, dut_prompt, aux_prompt,
                                          debug, timeout, campaign_number)
            elif architecture == 'a9':
                self.debugger = openocd(debugger_ip_address, self.rsakey,
                                        dut_serial_port, aux_serial_port,
                                        use_aux, dut_prompt, aux_prompt, debug,
                                        timeout, campaign_number)

    def close(self):
        if not self.use_simics:
            self.debugger.close()

    def setup_campaign(self, directory, architecture, application, arguments,
                       output_file, dut_files, aux_files, iterations,
                       aux_application, aux_arguments, use_aux_output,
                       num_checkpoints, kill_dut):
        campaign_data = {'campaign_number': self.campaign_number,
                         'application': application,
                         'output_file': output_file,
                         'use_aux': self.use_aux,
                         'use_aux_output': use_aux_output,
                         'architecture': architecture,
                         'use_simics': self.use_simics,
                         'timestamp': datetime.now(),
                         'kill_dut': kill_dut}
        self.kill_dut = kill_dut
        if self.use_simics:
            self.debugger.launch_simics()
        else:
            if self.use_aux:
                self.debugger.aux.serial.write('\x03')
                aux_process = Thread(target=self.debugger.aux.do_login)
                aux_process.start()
            self.debugger.reset_dut()
            if self.use_aux:
                aux_process.join()
        if arguments:
            self.command = application+' '+arguments
        else:
            self.command = application
        campaign_data['command'] = self.command
        if self.use_aux:
            if aux_arguments:
                self.aux_command = aux_application+' '+aux_arguments
            else:
                self.aux_command = aux_application
            campaign_data['aux_command'] = self.aux_command
        else:
            self.aux_command = ''
        files = []
        files.append(directory+'/'+application)
        if self.use_aux:
            files_aux = []
            files_aux.append(directory+'/'+aux_application)
        if dut_files:
            for item in dut_files.split(','):
                files.append(directory+'/'+item.lstrip().rstrip())
        if self.use_aux:
            if aux_files:
                for item in aux_files.split(','):
                    files_aux.append(directory+'/'+item.lstrip().rstrip())
        if self.use_aux:
            aux_process = Thread(target=self.debugger.aux.send_files,
                                 args=(files_aux, ))
            aux_process.start()
        self.debugger.dut.send_files(files)
        if self.use_aux:
            aux_process.join()
        if self.use_aux:
            aux_process = Thread(target=self.debugger.aux.command)
            aux_process.start()
        self.debugger.dut.command()
        if self.use_aux:
            aux_process.join()
        campaign_data['exec_time'], campaign_data['num_cycles'] = \
            self.debugger.time_application(self.command, self.aux_command,
                                           iterations, self.kill_dut)
        if self.use_simics:
            (campaign_data['cycles_between'],
             campaign_data['num_checkpoints']) = \
                self.debugger.create_checkpoints(self.command, self.aux_command,
                                                 campaign_data['num_cycles'],
                                                 num_checkpoints, self.kill_dut)
        if output_file:
            if use_aux_output:
                self.debugger.aux.get_file(output_file, 'campaign-data/' +
                                           str(self.campaign_number)+'/gold_' +
                                           output_file)
            else:
                self.debugger.dut.get_file(output_file, 'campaign-data/' +
                                           str(self.campaign_number)+'/gold_' +
                                           output_file)
        if self.use_simics:
            self.debugger.close()
        campaign_data['dut_output'] = self.debugger.dut.output
        campaign_data['debugger_output'] = self.debugger.output
        campaign_data['paramiko_output'] = self.debugger.dut.paramiko_output
        if self.use_aux:
            campaign_data['aux_output'] = self.debugger.aux.output
            campaign_data['aux_paramiko_output'] = \
                self.debugger.aux.paramiko_output
        sql_db = sqlite3.connect('campaign-data/db.sqlite3', timeout=60)
        sql = sql_db.cursor()
        insert_dict(sql, 'campaign', campaign_data)
        sql_db.commit()
        sql_db.close()
        if not self.use_simics:
            os.makedirs('campaign-data/'+str(self.campaign_number)+'/dut-files')
            for item in files:
                shutil.copy(item, 'campaign-data/'+str(self.campaign_number) +
                                  '/dut-files/')
            if self.use_aux:
                os.makedirs('campaign-data/'+str(self.campaign_number) +
                            '/aux-files')
                for item in files_aux:
                    shutil.copy(item, 'campaign-data/' +
                                      str(self.campaign_number)+'/aux-files/')
        self.close()

    def send_dut_files(self):
        files = []
        for item in os.listdir('campaign-data/'+str(self.campaign_number) +
                               '/dut-files'):
            files.append('campaign-data/'+str(self.campaign_number) +
                         '/dut-files/'+item)
        self.debugger.dut.send_files(files)

    def send_aux_files(self):
        files = []
        for item in os.listdir('campaign-data/'+str(self.campaign_number) +
                               '/aux-files'):
            files.append('campaign-data/'+str(self.campaign_number) +
                         '/aux-files/'+item)
        self.debugger.aux.send_files(files)

    def get_result_id(self, num_injections=0):
        result_data = {'campaign_id': self.campaign_number,
                       'iteration': self.iteration,
                       'num_injections': num_injections,
                       'outcome': 'In progress',
                       'outcome_category': 'Incomplete',
                       'timestamp': datetime.now()}
        sql_db = sqlite3.connect('campaign-data/db.sqlite3', timeout=60)
        sql = sql_db.cursor()
        insert_dict(sql, 'result', result_data)
        sql_db.commit()
        result_id = sql.lastrowid
        sql_db.close()
        return result_id

    def inject_faults(self, num_injections, selected_targets, compare_all):
        if self.use_simics:
            checkpoint_nums = range(1, self.num_checkpoints)
            injected_checkpoint_nums = []
            for i in xrange(num_injections):
                checkpoint_num = random.choice(checkpoint_nums)
                checkpoint_nums.remove(checkpoint_num)
                injected_checkpoint_nums.append(checkpoint_num)
            injected_checkpoint_nums = sorted(injected_checkpoint_nums)
            return self.debugger.inject_fault(self.result_id, self.iteration,
                                              injected_checkpoint_nums,
                                              selected_targets,
                                              self.cycles_between,
                                              self.num_checkpoints,
                                              compare_all)
        else:
            injection_times = []
            for i in xrange(num_injections):
                injection_times.append(random.uniform(0, self.exec_time))
            injection_times = sorted(injection_times)
            self.debugger.inject_fault(self.result_id, self.iteration,
                                       injection_times, self.command,
                                       selected_targets)
            return 0

    def check_output(self, output_file, use_aux_output):
        missing_output = False
        os.makedirs('campaign-data/'+str(self.campaign_number)+'/results/' +
                    str(self.iteration))
        result_folder = ('campaign-data/'+str(self.campaign_number) +
                         '/results/'+str(self.iteration))
        output_location = result_folder+'/'+output_file
        gold_location = ('campaign-data/'+str(self.campaign_number)+'/gold_' +
                         output_file)
        if use_aux_output:
            self.debugger.aux.get_file(output_file, output_location)
        else:
            self.debugger.dut.get_file(output_file, output_location)
        if not os.listdir(result_folder):
            os.rmdir(result_folder)
            missing_output = True
        else:
            with open(gold_location, 'r') as solution:
                solutionContents = solution.read()
            with open(output_location, 'r') as result:
                resultContents = result.read()
            self.data_diff = SequenceMatcher(None, solutionContents,
                                             resultContents).quick_ratio()
            if self.data_diff == 1.0:
                os.remove(output_location)
                if not os.listdir(result_folder):
                    os.rmdir(result_folder)
        if use_aux_output:
            self.debugger.aux.command('rm '+output_file)
        else:
            self.debugger.dut.command('rm '+output_file)
        if missing_output:
            raise DrSEUsError(DrSEUsError.missing_output)

    def monitor_execution(self, latent_faults, output_file, use_aux_output):
        buff = ''
        aux_buff = ''
        outcome = ''
        outcome_category = ''
        if self.use_aux:
            try:
                aux_buff = self.debugger.aux.read_until()
            except DrSEUsError as error:
                self.debugger.dut.serial.write('\x03')
                outcome = error.type
                outcome_category = 'AUX execution error'
            else:
                if self.kill_dut:
                    self.debugger.dut.serial.write('\x03')
        try:
            buff = self.debugger.dut.read_until()
        except DrSEUsError as error:
            outcome = error.type
            outcome_category = 'Execution error'
        for line in buff.split('\n'):
            if 'drseus_detected_errors:' in line:
                self.detected_errors = int(line.replace(
                                           'drseus_detected_errors:', ''))
                break
        if self.use_aux:
            for line in aux_buff.split('\n'):
                if 'drseus_detected_errors:' in line:
                    if self.detected_errors is None:
                        self.detected_errors = 0
                    self.detected_errors += int(line.replace(
                                                'drseus_detected_errors:', ''))
                    break
        if output_file and not outcome:
            try:
                self.check_output(output_file, use_aux_output)
            except DrSEUsError as error:
                if error.type == DrSEUsError.scp_error:
                    outcome = 'Error getting output file'
                    outcome_category = 'SCP error'
                elif error.type == DrSEUsError.missing_output:
                    outcome = 'Missing output file'
                    outcome_category = 'SCP error'
                else:
                    outcome = error.type
                    outcome_category = 'Post execution error'
        if not outcome:
            if self.detected_errors is not None and self.detected_errors > 0:
                outcome = 'Detected data error'
                outcome_category = 'Data error'
            elif self.data_diff is not None and self.data_diff < 1.0:
                outcome = 'Silent data error'
                outcome_category = 'Data error'
            elif latent_faults:
                outcome = 'Latent faults'
                outcome_category = 'No error'
            else:
                outcome = 'Masked faults'
                outcome_category = 'No error'
        return outcome, outcome_category

    def log_result(self, outcome, outcome_category):
        print(colored('iteration '+str(self.iteration)+' outcome: ' +
                      outcome_category+' - '+outcome, 'blue'), end='')
        if self.data_diff is not None and self.data_diff < 1.0:
            print(colored(', data diff: '+str(self.data_diff), 'blue'))
        else:
            print()
        result_data = {'outcome': outcome,
                       'outcome_category': outcome_category,
                       'data_diff': self.data_diff,
                       'detected_errors': self.detected_errors,
                       'dut_output': self.debugger.dut.output,
                       'paramiko_output': self.debugger.dut.paramiko_output,
                       'debugger_output': self.debugger.output,
                       'timestamp': datetime.now()}
        if self.use_aux:
            result_data['aux_output'] = self.debugger.aux.output
            result_data['aux_paramiko_output'] = \
                self.debugger.aux.paramiko_output
        sql_db = sqlite3.connect('campaign-data/db.sqlite3', timeout=60)
        sql = sql_db.cursor()
        update_dict(sql, 'result', result_data, self.result_id)
        sql_db.commit()
        sql_db.close()
        self.data_diff = None
        self.detected_errors = None
        self.debugger.output = ''
        self.debugger.dut.output = ''
        self.debugger.dut.paramiko_output = ''
        if self.use_aux:
            self.debugger.aux.output = ''
            self.debugger.aux.paramiko_output = ''

    def inject_and_monitor(self, iteration_counter, last_iteration,
                           num_injections, selected_targets, output_file,
                           use_aux_output, compare_all):
        self.data_diff = None
        self.detected_errors = None
        if self.use_aux and not self.use_simics:
            if self.use_aux:
                self.debugger.aux.serial.write('\x03')
                self.debugger.aux.do_login()
                self.send_aux_files()
        while True:
            with iteration_counter.get_lock():
                self.iteration = iteration_counter.value
                iteration_counter.value += 1
            if self.iteration >= last_iteration:
                break
            self.result_id = self.get_result_id(num_injections)
            if not self.use_simics:
                attempts = 5
                for attempt in xrange(attempts):
                    try:
                        self.debugger.reset_dut()
                    except DrSEUsError as error:
                        if attempt < attempts-1:
                            print(colored('error resetting DUT: '+error.type,
                                          'red'))
                            sleep(30)
                        else:
                            # fallback to power cycle
                            raise DrSEUsError(error.type)
                    else:
                        break
                try:
                    self.send_dut_files()
                except DrSEUsError:
                    self.log_result('Error sending files to DUT', 'SCP error')
                    continue
            if self.use_aux and not self.use_simics:
                self.debugger.aux.serial.write(str('./'+self.aux_command+'\n'))
            try:
                latent_faults = self.inject_faults(num_injections,
                                                   selected_targets,
                                                   compare_all)
                self.debugger.continue_dut()
            except DrSEUsError as error:
                outcome = error.type
                if self.use_simics:
                    outcome_category = 'Simics error'
                else:
                    outcome_category = 'Debugger error'
                    if not self.use_simics:
                        try:
                            self.debugger.continue_dut()
                            if self.use_aux:
                                aux_process = Thread(
                                    target=self.debugger.aux.read_until)
                                aux_process.start()
                            self.debugger.dut.read_until()
                            if self.use_aux:
                                aux_process.join()
                        except:
                            pass
            else:
                outcome, outcome_category = self.monitor_execution(
                    latent_faults, output_file, use_aux_output)
                if outcome == 'Latent faults' or (not self.use_simics
                                                  and outcome ==
                                                  'Masked faults'):
                    if self.use_aux:
                        self.debugger.aux.serial.write(str('./' +
                                                           self.aux_command +
                                                           '\n'))
                    self.debugger.dut.serial.write(str('./'+self.command+'\n'))
                    next_outcome = self.monitor_execution(0, output_file,
                                                          use_aux_output)[0]
                    if next_outcome != 'Masked faults':
                        outcome = next_outcome
                        outcome_category = 'Post execution error'
                    elif self.use_simics:
                        if self.debugger.persistent_faults(self.result_id):
                            outcome = 'Persistent faults'
            if self.use_simics:
                try:
                    self.debugger.close()
                except DrSEUsError as error:
                    outcome = error.type
                    outcome_category = 'Simics error'
                finally:
                    shutil.rmtree('simics-workspace/injected-checkpoints/' +
                                  str(self.campaign_number)+'/' +
                                  str(self.iteration))
            self.log_result(outcome, outcome_category)
        self.close()

    def supervise(self, starting_iteration, run_time, output_file,
                  use_aux_output, packet_capture):
        self.data_diff = None
        self.detected_errors = None
        iterations = int(run_time / self.exec_time)
        print(colored('performing '+str(iterations)+' iterations', 'blue'))
        if self.use_simics:
            self.debugger.launch_simics('gold-checkpoints/' +
                                        str(self.campaign_number)+'/' +
                                        str(self.num_checkpoints-1)+'_merged')
            self.debugger.continue_dut()
        else:
            if self.use_aux:
                self.debugger.aux.serial.write('\x03')
                aux_process = Thread(target=self.debugger.aux.do_login)
                aux_process.start()
            self.debugger.reset_dut()
            if self.use_aux:
                aux_process.join()
            self.send_dut_files()
            if self.use_aux:
                self.send_aux_files()
        for iteration in xrange(starting_iteration,
                                starting_iteration + iterations):
            self.iteration = iteration
            self.result_id = self.get_result_id()
            # create empty injection, used for injection charts in log viewer
            injection_data = {'result_id': self.result_id,
                              'injection_number': 0,
                              'timestamp': datetime.now()}
            sql_db = sqlite3.connect('campaign-data/db.sqlite3', timeout=60)
            sql = sql_db.cursor()
            insert_dict(sql, 'injection', injection_data)
            sql_db.commit()
            sql_db.close()
            if packet_capture:
                data_dir = ('campaign-data/'+str(self.campaign_number) +
                            '/results/'+str(self.iteration))
                os.makedirs(data_dir)
                capture_file = open(data_dir+'/capture.pcap', 'w')
                capture_process = subprocess.Popen(['ssh', 'p2020', 'tshark '
                                                    '-F pcap -i eth1 -w -'],
                                                   stderr=subprocess.PIPE,
                                                   stdout=capture_file)
                buff = ''
                while True:
                    buff += capture_process.stderr.read(1)
                    if buff[-len('Capturing on \'eth1\''):] == \
                            'Capturing on \'eth1\'':
                        break
            if self.use_aux:
                self.debugger.aux.serial.write(str('./'+self.aux_command+'\n'))
            self.debugger.dut.serial.write(str('./'+self.command+'\n'))
            outcome, outcome_category = self.monitor_execution(
                0, output_file, use_aux_output)
            self.log_result(outcome, outcome_category)
            if packet_capture:
                os.system('ssh p2020 \'killall tshark\'')
                capture_process.wait()
                capture_file.close()
        if self.use_simics:
            self.debugger.close()
        self.close()
