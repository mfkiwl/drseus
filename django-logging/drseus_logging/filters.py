from django.forms import SelectMultiple
import django_filters
from re import split

from .models import (injection, result, simics_register_diff)


def fix_sort(string):
    return ''.join([text.zfill(5) if text.isdigit() else text.lower() for
                    text in split('([0-9]+)', str(string[0]))])


def injection_choices(campaign, attribute):
    choices = []
    for item in sorted(injection.objects.filter(
            result__campaign_id=campaign).values(attribute).distinct()):
        choices.append((item[attribute], item[attribute]))
    return sorted(choices, key=fix_sort)


def result_choices(campaign, attribute):
    choices = []
    for item in sorted(result.objects.filter(
            campaign_id=campaign).values(attribute).distinct()):
        choices.append((item[attribute], item[attribute]))
    return sorted(choices, key=fix_sort)


class hw_result_filter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        campaign = kwargs['campaign']
        del kwargs['campaign']
        super(hw_result_filter, self).__init__(*args, **kwargs)
        bit_choices = injection_choices(campaign, 'bit')
        self.filters['injection__bit'].extra.update(choices=bit_choices)
        self.filters['injection__bit'].widget.attrs['size'] = min(
            len(bit_choices), 10)
        core_choices = injection_choices(campaign, 'core')
        self.filters['injection__core'].extra.update(choices=core_choices)
        self.filters['injection__core'].widget.attrs['size'] = min(
            len(core_choices), 10)
        injections_choices = result_choices(campaign, 'injections')
        self.filters['injections'].extra.update(choices=injections_choices)
        self.filters['injections'].widget.attrs['size'] = min(
            len(injections_choices), 10)
        outcome_choices = result_choices(campaign, 'outcome')
        self.filters['outcome'].extra.update(choices=outcome_choices)
        self.filters['outcome'].widget.attrs['size'] = min(
            len(outcome_choices), 10)
        outcome_category_choices = result_choices(campaign, 'outcome_category')
        self.filters['outcome_category'].extra.update(
            choices=outcome_category_choices)
        self.filters['outcome_category'].widget.attrs['size'] = min(
            len(outcome_category_choices), 10)
        register_choices = injection_choices(campaign, 'register')
        self.filters['injection__register'].extra.update(
            choices=register_choices)
        self.filters['injection__register'].widget.attrs['size'] = min(
            len(register_choices), 10)
        time_rounded_choices = injection_choices(campaign, 'time_rounded')
        self.filters['injection__time_rounded'].extra.update(
            choices=time_rounded_choices)
        self.filters['injection__time_rounded'].widget.attrs['size'] = min(
            len(time_rounded_choices), 10)

    injection__bit = django_filters.MultipleChoiceFilter(
        label='Bit',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__core = django_filters.MultipleChoiceFilter(
        label='Core',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__register = django_filters.MultipleChoiceFilter(
        label='Register',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__time_rounded = django_filters.MultipleChoiceFilter(
        label='Injection time',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injections = django_filters.MultipleChoiceFilter(
        label='Number of injections',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    outcome = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    outcome_category = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))

    class Meta:
        model = result
        exclude = ['aux_output', 'aux_paramiko_output', 'campaign', 'data_diff',
                   'debugger_output', 'detected_errors', 'dut_output',
                   'iteration', 'paramiko_output', 'timestamp']


class hw_injection_filter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        campaign = kwargs['campaign']
        del kwargs['campaign']
        super(hw_injection_filter, self).__init__(*args, **kwargs)
        bit_choices = injection_choices(campaign, 'bit')
        self.filters['bit'].extra.update(choices=bit_choices)
        self.filters['bit'].widget.attrs['size'] = min(len(bit_choices), 10)
        core_choices = injection_choices(campaign, 'core')
        self.filters['core'].extra.update(choices=core_choices)
        self.filters['core'].widget.attrs['size'] = min(len(core_choices), 10)
        injections_choices = result_choices(campaign, 'injections')
        self.filters['result__injections'].extra.update(
            choices=injections_choices)
        self.filters['result__injections'].widget.attrs['size'] = min(
            len(injections_choices), 10)
        outcome_choices = result_choices(campaign, 'outcome')
        self.filters['result__outcome'].extra.update(choices=outcome_choices)
        self.filters['result__outcome'].widget.attrs['size'] = min(
            len(outcome_choices), 10)
        outcome_category_choices = result_choices(campaign, 'outcome_category')
        self.filters['result__outcome_category'].extra.update(
            choices=outcome_category_choices)
        self.filters['result__outcome_category'].widget.attrs['size'] = min(
            len(outcome_category_choices), 10)
        register_choices = injection_choices(campaign, 'register')
        self.filters['register'].extra.update(choices=register_choices)
        self.filters['register'].widget.attrs['size'] = min(
            len(register_choices), 10)
        time_rounded_choices = injection_choices(campaign, 'time_rounded')
        self.filters['time_rounded'].extra.update(choices=time_rounded_choices)
        self.filters['time_rounded'].widget.attrs['size'] = min(
            len(time_rounded_choices), 10)

    bit = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    core = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    register = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__injections = django_filters.MultipleChoiceFilter(
        label='Number of injections',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__outcome = django_filters.MultipleChoiceFilter(
        label='Outcome',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__outcome_category = django_filters.MultipleChoiceFilter(
        label='Outcome category',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    time_rounded = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))

    class Meta:
        model = result
        exclude = ['aux_output', 'aux_paramiko_output', 'campaign', 'data_diff',
                   'debugger_output', 'detected_errors', 'dut_output',
                   'iteration', 'outcome', 'outcome_category',
                   'paramiko_output', 'timestamp']


class simics_result_filter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        campaign = kwargs['campaign']
        del kwargs['campaign']
        super(simics_result_filter, self).__init__(*args, **kwargs)
        bit_choices = injection_choices(campaign, 'bit')
        self.filters['injection__bit'].extra.update(choices=bit_choices)
        self.filters['injection__bit'].widget.attrs['size'] = min(
            len(bit_choices), 10)
        checkpoint_number_choices = injection_choices(
            campaign, 'checkpoint_number')
        self.filters['injection__checkpoint_number'].extra.update(
            choices=checkpoint_number_choices)
        self.filters['injection__checkpoint_number'].widget.attrs['size'] = min(
            len(checkpoint_number_choices), 10)
        injections_choices = result_choices(campaign, 'injections')
        self.filters['injections'].extra.update(choices=injections_choices)
        self.filters['injections'].widget.attrs['size'] = min(
            len(injections_choices), 10)
        outcome_choices = result_choices(campaign, 'outcome')
        self.filters['outcome'].extra.update(choices=outcome_choices)
        self.filters['outcome'].widget.attrs['size'] = min(
            len(outcome_choices), 10)
        outcome_category_choices = result_choices(campaign, 'outcome_category')
        self.filters['outcome_category'].extra.update(
            choices=outcome_category_choices)
        self.filters['outcome_category'].widget.attrs['size'] = min(
            len(outcome_category_choices), 10)
        register_choices = injection_choices(campaign, 'register')
        self.filters['injection__register'].extra.update(
            choices=register_choices)
        self.filters['injection__register'].widget.attrs['size'] = min(
            len(register_choices), 10)
        register_index_choices = injection_choices(campaign, 'register_index')
        self.filters['injection__register_index'].extra.update(
            choices=register_index_choices)
        self.filters['injection__register_index'].widget.attrs['size'] = min(
            len(register_index_choices), 10)
        target_choices = injection_choices(campaign, 'target')
        self.filters['injection__target'].extra.update(
            choices=target_choices)
        self.filters['injection__target'].widget.attrs['size'] = min(
            len(target_choices), 10)
        target_index_choices = injection_choices(campaign, 'target_index')
        self.filters['injection__target_index'].extra.update(
            choices=target_index_choices)
        self.filters['injection__target_index'].widget.attrs['size'] = min(
            len(target_index_choices), 10)

    injection__bit = django_filters.MultipleChoiceFilter(
        label='Bit',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__checkpoint_number = django_filters.MultipleChoiceFilter(
        label='Checkpoint number',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__register = django_filters.MultipleChoiceFilter(
        label='Register',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__register_index = django_filters.MultipleChoiceFilter(
        label='Register index',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__target = django_filters.MultipleChoiceFilter(
        label='Target',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injection__target_index = django_filters.MultipleChoiceFilter(
        label='Target index',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    injections = django_filters.MultipleChoiceFilter(
        label='Number of injections',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    outcome = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    outcome_category = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))

    class Meta:
        model = result
        exclude = ['aux_output', 'aux_paramiko_output', 'campaign', 'data_diff',
                   'debugger_output', 'detected_errors', 'dut_output',
                   'iteration', 'paramiko_output', 'timestamp']


class simics_injection_filter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        campaign = kwargs['campaign']
        del kwargs['campaign']
        super(simics_injection_filter, self).__init__(*args, **kwargs)
        bit_choices = injection_choices(campaign, 'bit')
        self.filters['bit'].extra.update(choices=bit_choices)
        self.filters['bit'].widget.attrs['size'] = min(len(bit_choices), 10)
        checkpoint_number_choices = injection_choices(
            campaign, 'checkpoint_number')
        self.filters['checkpoint_number'].extra.update(
            choices=checkpoint_number_choices)
        self.filters['checkpoint_number'].widget.attrs['size'] = min(
            len(checkpoint_number_choices), 10)
        injections_choices = result_choices(campaign, 'injections')
        self.filters['result__injections'].extra.update(
            choices=injections_choices)
        self.filters['result__injections'].widget.attrs['size'] = min(
            len(injections_choices), 10)
        outcome_choices = result_choices(campaign, 'outcome')
        self.filters['result__outcome'].extra.update(choices=outcome_choices)
        self.filters['result__outcome'].widget.attrs['size'] = min(
            len(outcome_choices), 10)
        outcome_category_choices = result_choices(campaign, 'outcome_category')
        self.filters['result__outcome_category'].extra.update(
            choices=outcome_category_choices)
        self.filters['result__outcome_category'].widget.attrs['size'] = min(
            len(outcome_category_choices), 10)
        register_choices = injection_choices(campaign, 'register')
        self.filters['register'].extra.update(choices=register_choices)
        self.filters['register'].widget.attrs['size'] = min(
            len(register_choices), 10)
        register_index_choices = injection_choices(campaign, 'register_index')
        self.filters['register_index'].extra.update(
            choices=register_index_choices)
        self.filters['register_index'].widget.attrs['size'] = min(
            len(register_index_choices), 10)
        target_choices = injection_choices(campaign, 'target')
        self.filters['target'].extra.update(choices=target_choices)
        self.filters['target'].widget.attrs['size'] = min(
            len(target_choices), 10)
        target_index_choices = injection_choices(campaign, 'target_index')
        self.filters['target_index'].extra.update(choices=target_index_choices)
        self.filters['target_index'].widget.attrs['size'] = min(
            len(target_index_choices), 10)

    bit = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    checkpoint_number = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    register = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    register_index = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__injections = django_filters.MultipleChoiceFilter(
        label='Number of injections',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__outcome = django_filters.MultipleChoiceFilter(
        label='Outcome',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    result__outcome_category = django_filters.MultipleChoiceFilter(
        label='Outcome category',
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    target = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    target_index = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))

    class Meta:
        model = injection
        exclude = ['checkpoint_number', 'config_object', 'config_type', 'core',
                   'field', 'gold_value', 'injected_value', 'injection_number',
                   'result', 'time', 'time_rounded',  'timestamp']


class simics_register_diff_filter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        self.campaign = kwargs['campaign']
        del kwargs['campaign']
        super(simics_register_diff_filter, self).__init__(*args, **kwargs)
        self.queryset = kwargs['queryset']
        checkpoint_number_choices = self.simics_register_diff_choices(
            'checkpoint_number')
        self.filters['checkpoint_number'].extra.update(
            choices=checkpoint_number_choices)
        self.filters['checkpoint_number'].widget.attrs['size'] = min(
            len(checkpoint_number_choices), 10)
        register_choices = self.simics_register_diff_choices('register')
        self.filters['register'].extra.update(choices=register_choices)
        self.filters['register'].widget.attrs['size'] = min(
            len(register_choices), 30)

    def simics_register_diff_choices(self, attribute):
        choices = []
        for item in sorted(self.queryset.filter(
            result__campaign_id=self.campaign
                ).values(attribute).distinct()):
            choices.append((item[attribute], item[attribute]))
        return sorted(choices, key=fix_sort)

    checkpoint_number = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))
    register = django_filters.MultipleChoiceFilter(
        widget=SelectMultiple(attrs={'style': 'width:100%;'}))

    class Meta:
        model = simics_register_diff
        exclude = ['config_object', 'gold_value', 'monitored_value', 'result']
