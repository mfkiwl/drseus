"""
Copyright (c) 2018 NSF Center for Space, High-performance, and Resilient Computing (SHREC)
University of Pittsburgh. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided
that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS AS IS AND ANY EXPRESS OR IMPLIED WARRANTIES, 
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT 
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
OF SUCH DAMAGE.
"""

from datetime import datetime
from django.core.management import execute_from_command_line as django_command
from django.db.utils import OperationalError, ProgrammingError
from getpass import getuser
from io import StringIO
from os import mkdir, remove
from os.path import exists
from paramiko import RSAKey
from subprocess import check_output, DEVNULL, PIPE, Popen
from sys import argv
from sys import stdout as sys_stdout
from termcolor import colored
from time import sleep
from traceback import format_exc, format_stack, print_exc

from .log.models import campaign as campaign_model


def initialize_database(options):
    if options.db_postgresql:
        commands = (
            'CREATE USER {} WITH PASSWORD \'{}\';'.format(options.db_user,
                                                          options.db_password),
            'ALTER ROLE {} SET client_encoding TO \'utf8\';'.format(
                options.db_user),
            'ALTER ROLE {} SET default_transaction_isolation '
            'TO \'read committed\';'.format(options.db_user),
            'ALTER ROLE {} SET timezone TO \'UTC\';'.format(options.db_user),
            'CREATE DATABASE {} WITH OWNER {}'.format(options.db_name,
                                                      options.db_user))
        __psql(options, superuser=True, commands=commands)
        django_command([argv[0], 'makemigrations', 'log'])
    elif not exists('campaign-data'):
        mkdir('campaign-data')
    django_command([argv[0], 'migrate'])


def get_campaign(options):
    if options == 'all':
        return campaign_model.objects.all().order_by('id')
    elif options.campaign_description is not None:
        if campaign_model.objects.filter(
                description=options.campaign_description).count() > 1:
            raise Exception(
                'more than one campaign with the specifed description exists, '
                'specify a campaign id instead')
        return campaign_model.objects.get(
            description=options.campaign_description)
    elif not options.campaign_id:
        return campaign_model.objects.latest('id')
    else:
        return campaign_model.objects.get(id=options.campaign_id)


def new_campaign(options):
    rsakey_file = StringIO()
    RSAKey.generate(1024).write_private_key(rsakey_file)
    rsakey = rsakey_file.getvalue()
    rsakey_file.close()
    campaign_kwargs = {
        'architecture': options.architecture,
        'aux': options.aux,
        'caches': options.caches,
        'command': options.dut_command,
        'description': options.description,
        'log_files': options.log_files,
        'output_file': options.output_file,
        'rsakey': rsakey,
        'simics': options.simics
    }
    if options.aux:
        campaign_kwargs.update({
            'aux_command': options.aux_command,
            'aux_log_files': options.aux_log_files,
            'aux_output_file': options.aux_output_file,
            'kill_aux': options.kill_aux,
            'kill_dut': options.kill_dut
        })
    campaign = campaign_model(**campaign_kwargs)
    try:
        campaign.save()
    except OperationalError:
        initialize_database(options)
        campaign.save()
    except ProgrammingError:
        print_exc()
        print('the database appears to be corrupted')
        return
    return campaign


def __psql(options, executable='psql', superuser=False, database=False,
           args=[], commands=[], stdin=None, stdout=None):
        if commands and stdin is not None:
            print('cannot simultaneously send commands and redirect stdin, '
                  'ignoring stdin redirect')
        popen_command = []
        if superuser and options.db_superuser != getuser() and \
                options.db_superuser_password is None:
            print('running "{}" with sudo, password may be required'.format(
                executable))
            popen_command.extend(['sudo', '-u', options.db_superuser])
        popen_command.append(executable)
        if options.db_host != 'localhost' or \
                not (superuser and options.db_superuser_password is None):
            popen_command.extend(['-h', options.db_host, '-W'])
            password_prompt = True
        else:
            password_prompt = False
        popen_command.extend(['-p', str(options.db_port)])
        if not superuser:
            popen_command.extend(['-U', options.db_user])
        if database:
            popen_command.extend(['-d', options.db_name])
        if args:
            popen_command.extend(args)
        kwargs = {}
        if commands:
            kwargs.update({'stdin': PIPE, 'universal_newlines': True})
        elif stdin:
            kwargs['stdin'] = stdin
        if stdout:
            kwargs['stdout'] = stdout
        process = Popen(popen_command, **kwargs)
        if commands:
            for command in commands:
                print('{}> {}'.format(executable, command))
                process.stdin.write('{}\n'.format(command))
            process.stdin.close()
        if password_prompt:
            print('user', end=' ')
            if superuser:
                print(options.db_superuser, end=' ')
            else:
                print(options.db_user, end=' ')
            sys_stdout.flush()
        process.wait()
        if process.returncode:
            raise Exception('{} error'.format(executable))


def delete_database(options):
    if options.db_postgresql:
        commands = ['DROP DATABASE {};'.format(options.db_name)]
        if options.delete_user:
            commands.append('DROP USER {};'.format(options.db_user))
        __psql(options,
               superuser=options.delete_user or options.db_host == 'localhost',
               commands=commands)
    else:
        if exists(options.db_file):
            remove(options.db_file)


def backup_database(options, backup_file):
    with open(backup_file, 'w') as backup:
        __psql(options, superuser=options.db_host == 'localhost',
               executable='pg_dump', database=True, args=['-c'], stdout=backup)


def restore_database(options, backup_file):
    for line in check_output(['sudo', '-u', options.db_superuser, 'psql', '-l'],
                             universal_newlines=True).split('\n'):
        if options.db_name in line.split('|')[0]:
            if input('database exists, continuing will overwrite it. continue? '
                     '[y/N]: ') not in ['y', 'Y', 'yes', 'Yes', 'YES']:
                return
            else:
                break
    else:
        initialize_database(options)
    with open(backup_file, 'r') as backup:
        __psql(options, superuser=True, database=True,
               args=['--single-transaction'], stdin=backup, stdout=DEVNULL)


class database(object):
    log_exception = '__LOG_EXCEPTION__'
    log_trace = '__LOG_TRACE__'

    def __init__(self, options):
        self.options = options
        self.campaign = get_campaign(options)
        self.result = None
        if options.command != 'new':
            self.__create_result(supervisor=options.command == 'supervise')

    def __create_result(self, supervisor=False):
        self.result = self.campaign.result_set.create(
            outcome_category=('Supervisor' if supervisor else 'Incomplete'),
            outcome=('' if supervisor else 'In progress'),
            dut_dev_serial=self.options.dut_dev_serial,
            dut_serial_port=self.options.dut_serial_port,
            aux_serial_port=self.options.aux_serial_port,
            previous_result=self.result)

    def log_result(self, supervisor=False, exit=False):
        if self.result.dut_serial_port is None:
            self.result.dut_serial_port = self.options.dut_serial_port
        if self.result.dut_dev_serial is None:
            self.result.dut_dev_serial = self.options.dut_dev_serial
        if self.result.aux_serial_port is None:
            self.result.aux_serial_port = self.options.aux_serial_port
        if self.result.outcome_category != 'DrSEUs' and \
                self.result.outcome != 'Exited':
            if self.result.dut_serial_port:
                out = '{}, '.format(self.result.dut_serial_port)
            else:
                out = ''
            out += '{}: {} - {}'.format(self.result.id,
                                        self.result.outcome_category,
                                        self.result.outcome)
            if self.result.data_diff is not None and \
                    self.result.data_diff < 1.0:
                out += ' {0:.2f}%'.format(min(self.result.data_diff*100,
                                              99.990))
            print(colored(out, 'blue'))
        self.result.timestamp = datetime.now()
        self.save()
        if not exit:
            self.__create_result(supervisor)

    def log_event(self, level, source, type_, description=None,
                  success=None, campaign=False):
        if description == self.log_trace:
            description = ''.join(format_stack()[:-2])
        elif description == self.log_exception:
            description = ''.join(format_exc())
        campaign = campaign or self.result is None
        event = (self.campaign if campaign else self.result).event_set.create(
            description=description,
            type=type_,
            level=level,
            source=source,
            success=success)
        return event

    def log_diff(self, checkpoint, config_object, register, gold_value,
                 monitored_value, attempts=10):
        for attempt in range(attempts):
            try:
                self.result.simics_register_diff_set.create(
                    checkpoint=checkpoint, config_object=config_object,
                    register=register, gold_value=gold_value,
                    monitored_value=monitored_value)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except Exception as error:
                print_exc()
                print(colored(
                    'Error saving diff to database (attempt {}/{}): {}'.format(
                        attempt+1, attempts, error), 'red'))
                if attempt < attempts-1:
                    sleep(30)
                else:
                    raise Exception('Error saving diff to database')
            else:
                break

    def save(self, attempts=10):
        for attempt in range(attempts):
            try:
                if self.result is None:
                    self.campaign.save()
                else:
                    self.result.save()
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except Exception as error:
                print_exc()
                print(colored(
                    'Error saving {} (attempt {}/{}): {}'.format(
                        'result' if self.result is not None else 'campaign',
                        attempt+1, attempts, error), 'red'))
                if attempt < attempts-1:
                    sleep(30)
                else:
                    raise Exception('Error saving {}'.format(
                        'result' if self.result is not None else 'campaign'))
            else:
                break
