import django_tables2 as tables
from .models import (campaign_data, result, injection, simics_register_diff,
                     simics_memory_diff)


class campaign_data_table(tables.Table):
    results = tables.Column()
    timestamp = tables.DateTimeColumn(format='m/d/Y H:i:s.u')

    class Meta:
        model = campaign_data
        attrs = {"class": "paleblue"}
        exclude = ('dut_output', 'debugger_output', 'aux_output',
                   'paramiko_output', 'aux_paramiko_output')


class result_table(tables.Table):
    iteration = tables.TemplateColumn(
        '<a href="/result/{{record.iteration}}">{{record.iteration}}</a>')
    injections = tables.Column()
    timestamp = tables.DateTimeColumn(format='m/d/Y H:i:s.u')

    class Meta:
        model = result
        attrs = {"class": "paleblue"}
        exclude = ('campaign_data', 'debugger_output', 'dut_output',
                   'aux_output', 'paramiko_output', 'aux_paramiko_output')


class hw_injection_table(tables.Table):
    timestamp = tables.DateTimeColumn(format='m/d/Y H:i:s.u')

    class Meta:
        model = injection
        attrs = {"class": "paleblue"}
        exclude = ('id', 'result', 'checkpoint_number', 'target_index',
                   'target', 'config_object', 'config_type', 'register_index',
                   'field')


class simics_injection_table(tables.Table):
    timestamp = tables.DateTimeColumn(format='m/d/Y H:i:s.u')

    class Meta:
        model = injection
        attrs = {"class": "paleblue"}
        exclude = ('id', 'result', 'core', 'time', 'time_rounded')


class simics_register_diff_table(tables.Table):
    class Meta:
        attrs = {"class": "paleblue"}
        exclude = ('id', 'result')
        model = simics_register_diff


class simics_memory_diff_table(tables.Table):
    class Meta:
        attrs = {"class": "paleblue"}
        exclude = ('id', 'result')
        model = simics_memory_diff
