from django_tables2 import (CheckBoxColumn, Column, DateTimeColumn, Table,
                            TemplateColumn)

from . import models

datetime_format = 'M j, Y h:i:s A'


class campaigns(Table):
    links = TemplateColumn(
        '<a href="/campaign/{{ record.id }}/info">'
        '<i class="fa fa-info"></i></a> &nbsp;'
        '<a href="/campaign/{{ record.id }}/results">'
        '<i class="fa fa-list"></i></a> &nbsp;'
        '<a href="/campaign/{{ record.id }}/events">'
        '<i class="fa fa-calendar"></i></a> &nbsp;'
        '<a href="/campaign/{{ record.id }}/injections">'
        '<i class="fa fa-crosshairs"></i></a> &nbsp;'
        '<a href="/campaign/{{ record.id }}/category_charts">'
        '<i class="fa fa-bar-chart"></i></a>', orderable=False)
    results = Column(empty_values=(), orderable=False)
    timestamp = DateTimeColumn(format=datetime_format)

    def render_cycles(self, record):
        return '{:,}'.format(record.cycles)

    def render_execution_time(self, record):
        return '{0:.4f}'.format(record.execution_time)

    def render_results(self, record):
        return '{:,}'.format(
            models.result.objects.filter(campaign=record.id).count())

    class Meta:
        fields = ('links', 'id', 'results', 'command', 'architecture', 'simics',
                  'execution_time', 'cycles', 'timestamp')
        model = models.campaign
        order_by = 'id'
        template = 'django_tables2/bootstrap.html'


class campaign(Table):
    results = Column(empty_values=(), orderable=False)
    timestamp = DateTimeColumn(format=datetime_format)

    def render_checkpoints(self, record):
        return '{:,}'.format(record.checkpoints)

    def render_cycles(self, record):
        return '{:,}'.format(record.cycles)

    def render_cycles_between(self, record):
        return '{:,}'.format(record.cycles_between)

    def render_execution_time(self, record):
        return '{0:.4f}'.format(record.execution_time)

    def render_results(self, record):
        return '{:,}'.format(
            models.result.objects.filter(campaign=record.id).count())

    class Meta:
        fields = ('id', 'timestamp', 'results', 'command', 'aux_command',
                  'description', 'architecture', 'simics', 'aux',
                  'execution_time', 'cycles', 'output_file', 'checkpoints',
                  'cycles_between')
        model = models.campaign
        orderable = False
        template = 'django_tables2/bootstrap.html'


class results(Table):
    id_ = TemplateColumn(  # LinkColumn()
        '<a href="/result/{{ value }}">{{ value }}</a>', accessor='id')
    registers = Column(empty_values=(), orderable=False)
    select_box = CheckBoxColumn(
        accessor='id',
        attrs={'th__input': {'onclick': 'update_selection(this)'}})
    timestamp = DateTimeColumn(format=datetime_format)
    targets = Column(empty_values=(), orderable=False)

    def render_cycles(self, record):
        return '{:,}'.format(record.cycles)

    def render_data_diff(self, record):
        return '{0:.2f}%'.format(record.data_diff*100)

    def render_execution_time(self, record):
        return '{0:.4f}'.format(record.execution_time)

    def render_registers(self, record):
        if record is not None:
            registers = [injection.register_alias if injection.register_alias
                         else injection.register for injection
                         in record.injection_set.all()]
        else:
            return '-'
        for index in range(len(registers)):
            if registers[index] is None:
                registers[index] = '-'
        if len(registers) > 0:
            return ', '.join(registers)
        else:
            return '-'

    def render_targets(self, record):
        if record is not None:
            targets = list(record.injection_set.values_list('target',
                                                            flat=True))
        else:
            return '-'
        for index in range(len(targets)):
            if targets[index] is None:
                targets[index] = '-'
        if len(targets) > 0:
            return ', '.join(targets)
        else:
            return '-'

    class Meta:
        fields = ('select_box', 'id_', 'dut_serial_port', 'timestamp',
                  'outcome_category', 'outcome', 'execution_time', 'cycles',
                  'data_diff', 'targets', 'registers')
        model = models.result
        order_by = '-id_'
        template = 'django_tables2/bootstrap.html'


class result(Table):
    outcome = TemplateColumn(
        '<input id="edit_outcome" type="text" value="{{ value }}" />')
    outcome_category = TemplateColumn(
        '<input id="edit_outcome_category" type="text" value="{{ value }}" />')
    timestamp = DateTimeColumn(format=datetime_format)

    def render_cycles(self, record):
        return '{:,}'.format(record.cycles)

    def render_data_diff(self, record):
        return '{0:.2f}%'.format(record.data_diff*100)

    def render_execution_time(self, record):
        return '{0:.4f}'.format(record.execution_time)

    class Meta:
        fields = ('dut_serial_port', 'timestamp', 'outcome_category', 'outcome',
                  'execution_time', 'cycles', 'num_injections', 'data_diff',
                  'detected_errors')
        model = models.result
        orderable = False
        template = 'django_tables2/bootstrap.html'


class events(Table):
    description = TemplateColumn(
        '{% if value %}<code class="console">{{ value }}</code>{% endif %}')
    result_id = TemplateColumn(
        '{% if value %}<a href="/result/{{ value }}">{{ value }}</a>'
        '{% else %}<a href="/campaign/{{ record.campaign_id }}/info">'
        'Campaign</a>{% endif %}',
        accessor='result_id')
    select_box = CheckBoxColumn(
        accessor='result_id',
        attrs={'th__input': {'onclick': 'update_selection(this)'}})
    success_ = TemplateColumn(
        '{% if value == None %}-'
        '{% elif value %}<span class="true">\u2714</span>'
        '{% else %}<span class="false">\u2718</span>{% endif %}',
        accessor='success')
    timestamp = DateTimeColumn(format=datetime_format)

    class Meta:
        fields = ('select_box', 'result_id', 'timestamp', 'level', 'source',
                  'type', 'success_', 'description')
        model = models.event
        order_by = ('result_id', 'timestamp')
        template = 'django_tables2/bootstrap.html'


class event(Table):
    description = TemplateColumn(
        '{% if value %}<code class="console">{{ value }}</code>{% endif %}')
    success_ = TemplateColumn(
        '{% if value == None %}-'
        '{% elif value %}<span class="true">\u2714</span>'
        '{% else %}<span class="false">\u2718</span>{% endif %}',
        accessor='success')
    timestamp = DateTimeColumn(format=datetime_format)

    class Meta:
        fields = ('timestamp', 'level', 'source', 'type', 'success_',
                  'description')
        model = models.event
        order_by = 'timestamp'
        template = 'django_tables2/bootstrap.html'


class injections(Table):
    result_id = TemplateColumn(
        '{% if value %}<a href="/result/{{ value }}">{{ value }}</a>'
        '{% else %}<a href="/campaign/{{ record.campaign_id }}/info">'
        'Campaign</a>{% endif %}',
        accessor='result_id')
    success_ = TemplateColumn(
        '{% if value == None %}-'
        '{% elif value %}<span class="true">\u2714</span>'
        '{% else %}<span class="false">\u2718</span>{% endif %}',
        accessor='success')

    class Meta:
        fields = ('result_id', 'target', 'target_index', 'register',
                  'register_index', 'bit', 'field', 'register_access',
                  'processor_mode', 'gold_value', 'injected_value', 'success_')
        model = models.injection
        order_by = ('target', 'target_index', 'register', 'register_index',
                    'bit', 'success')
        template = 'django_tables2/bootstrap.html'


class hw_injection(Table):
    success_ = TemplateColumn(
        '{% if value == None %}-'
        '{% elif value %}<span class="true">\u2714</span>'
        '{% else %}<span class="false">\u2718</span>{% endif %}',
        accessor='success')
    timestamp = DateTimeColumn(format=datetime_format)

    def render_time(self, record):
        return '{0:.6f}'.format(record.time)

    class Meta:
        fields = ('timestamp', 'time', 'target', 'target_index', 'register',
                  'register_index', 'bit', 'field', 'register_access',
                  'gold_value', 'injected_value', 'success_')
        model = models.injection
        order_by = 'time'
        template = 'django_tables2/bootstrap.html'


class simics_injection(Table):
    success_ = TemplateColumn(
        '{% if value == None %}-'
        '{% elif value %}<span class="true">\u2714</span>'
        '{% else %}<span class="false">\u2718</span>{% endif %}',
        accessor='success')
    timestamp = DateTimeColumn(format=datetime_format)

    class Meta:
        fields = ('timestamp', 'checkpoint', 'target', 'target_index',
                  'register', 'register_index', 'register_alias', 'bit',
                  'field', 'gold_value', 'injected_value', 'success_')
        model = models.injection
        order_by = 'checkpoint'
        template = 'django_tables2/bootstrap.html'


class simics_register_diff(Table):
    class Meta:
        fields = ('checkpoint', 'config_object', 'register', 'gold_value',
                  'monitored_value')
        model = models.simics_register_diff
        template = 'django_tables2/bootstrap.html'


class simics_memory_diff(Table):
    class Meta:
        fields = ('checkpoint', 'image_index', 'block')
        model = models.simics_memory_diff
        template = 'django_tables2/bootstrap.html'