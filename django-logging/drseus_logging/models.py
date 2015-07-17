from django.db import models


class campaign_data_manager(models.Manager):
    def get_queryset(self):
        return super(campaign_data_manager, self).get_queryset().annotate(
            results=models.Count('result'))


class campaign_data(models.Model):
    application = models.TextField()
    output_file = models.TextField()
    command = models.TextField()
    aux_command = models.TextField()
    use_aux_output = models.BooleanField()
    exec_time = models.FloatField()
    architecture = models.TextField()
    use_simics = models.BooleanField()
    use_aux = models.BooleanField()
    dut_output = models.TextField()
    aux_output = models.TextField()
    debugger_output = models.TextField()
    paramiko_output = models.TextField()
    aux_paramiko_output = models.TextField()
    num_cycles = models.IntegerField()
    num_checkpoints = models.IntegerField()
    cycles_between = models.IntegerField()
    timestamp = models.DateTimeField()
    objects = campaign_data_manager()


class result_manager(models.Manager):
    def get_queryset(self):
        return super(result_manager, self).get_queryset().annotate(
            injections=models.Count('injection'))


class result(models.Model):
    campaign_data = models.ForeignKey(campaign_data)
    iteration = models.IntegerField(primary_key=True)
    outcome = models.TextField()
    outcome_category = models.TextField()
    data_diff = models.FloatField()
    detected_errors = models.IntegerField()
    dut_output = models.TextField()
    aux_output = models.TextField()
    debugger_output = models.TextField()
    paramiko_output = models.TextField()
    aux_paramiko_output = models.TextField()
    timestamp = models.DateTimeField()
    objects = result_manager()


class injection_manager(models.Manager):
    def get_queryset(self):
        return super(injection_manager, self).get_queryset().filter(
            result__campaign_data_id__gt=0)


class injection(models.Model):
    # commond fields
    result = models.ForeignKey(result)
    injection_number = models.IntegerField()
    register = models.TextField()
    bit = models.IntegerField()
    gold_value = models.TextField()
    injected_value = models.TextField()
    timestamp = models.DateTimeField()
    # hw fields
    time = models.FloatField(null=True)
    time_rounded = models.FloatField(null=True)
    core = models.IntegerField(null=True)
    # simics fields
    checkpoint_number = models.IntegerField(null=True)
    target_index = models.TextField(null=True)
    target = models.TextField(null=True)
    config_object = models.TextField(null=True)
    config_type = models.TextField(null=True)
    register_index = models.TextField(null=True)
    field = models.TextField(null=True)
    # gold_debug_info = models.TextField(null=True)
    objects = injection_manager()


class simics_register_diff(models.Model):
    result = models.ForeignKey(result)
    checkpoint_number = models.IntegerField()
    config_object = models.TextField()
    register = models.TextField()
    gold_value = models.TextField()
    monitored_value = models.TextField()


class simics_memory_diff(models.Model):
    result = models.ForeignKey(result)
    checkpoint_number = models.IntegerField()
    image_index = models.IntegerField()
    block = models.TextField()
