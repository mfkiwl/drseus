from copy import deepcopy
from django.db.models import Avg, Case, IntegerField, Sum, When
from numpy import convolve, ones
from json import dumps
from time import time

from log.charts import colors, colors_extra


def outcomes(**kwargs):
    chart_data = kwargs['chart_data']
    chart_list = kwargs['chart_list']
    injections = kwargs['injections']
    group_categories = kwargs['group_categories']
    order = kwargs['order']
    outcomes = kwargs['outcomes']

    start = time()
    injections = injections.exclude(checkpoint__isnull=True)
    checkpoints = list(injections.values_list(
        'checkpoint', flat=True).distinct().order_by('checkpoint'))
    if len(checkpoints) < 1:
        return
    extra_colors = list(colors_extra)
    chart = {
        'chart': {
            'renderTo': 'checkpoints_chart_raw',
            'type': 'column',
            'zoomType': 'xy'
        },
        'colors': [colors[outcome] if outcome in colors else extra_colors.pop()
                   for outcome in outcomes],
        'credits': {
            'enabled': False
        },
        'exporting': {
            'filename': 'checkpoints_chart_raw',
            'sourceWidth': 960,
            'sourceHeight': 540,
            'scale': 2
        },
        'plotOptions': {
            'series': {
                'point': {
                    'events': {
                        'click': 'click_function'
                    }
                },
                'stacking': True
            }
        },
        'series': [],
        'title': {
            'text': None
        },
        'xAxis': {
            'categories': checkpoints,
            'title': {
                'text': 'Injected Checkpoint'
            }
        },
        'yAxis': {
            'title': {
                'text': 'Total Injections'
            }
        }
    }
    window_size = 10
    chart_smoothed = deepcopy(chart)
    chart_smoothed['chart']['type'] = 'area'
    chart_smoothed['chart']['renderTo'] = 'checkpoints_chart'
    for outcome in outcomes:
        when_kwargs = {'then': 1}
        when_kwargs['result__outcome_category' if group_categories
                    else 'result__outcome'] = outcome
        data = list(injections.values_list(
            'checkpoint').distinct().order_by('checkpoint').annotate(
                count=Sum(Case(When(**when_kwargs),
                               default=0, output_field=IntegerField()))
            ).values_list('count', flat=True))
        chart['series'].append({'data': data, 'name': outcome})
        chart_smoothed['series'].append({
            'data': convolve(
                data, ones(window_size)/window_size, 'same').tolist(),
            'name': outcome,
            'stacking': True})
    chart_data.append(dumps(chart_smoothed, indent=4))
    chart = dumps(chart, indent=4).replace('\"click_function\"', """
    function(event) {
        window.location.assign('results?outcome='+this.series.name+
                               '&injection__checkpoint='+this.category);
    }
    """.replace('\n    ', '\n                        '))
    if group_categories:
        chart = chart.replace('?outcome=', '?outcome_category=')
    chart_data.append(chart)
    chart_list.append(('checkpoints_chart', 'Injections Over Time', True,
                       order))
    print('checkpoints_charts', round(time()-start, 2), 'seconds')


def data_diff(**kwargs):
    chart_data = kwargs['chart_data']
    chart_list = kwargs['chart_list']
    injections = kwargs['injections']
    order = kwargs['order']

    start = time()
    injections = injections.exclude(checkpoint__isnull=True)
    checkpoints = list(injections.values_list(
        'checkpoint', flat=True).distinct().order_by('checkpoint'))
    if len(checkpoints) < 1:
        return
    chart = {
        'chart': {
            'renderTo': 'diff_checkpoints_chart',
            'type': 'column',
            'zoomType': 'xy'
        },
        'colors': ('#008080', ),
        'credits': {
            'enabled': False
        },
        'exporting': {
            'filename': 'diff_checkpoints_chart',
            'sourceWidth': 960,
            'sourceHeight': 540,
            'scale': 2
        },
        'legend': {
            'enabled': False
        },
        'plotOptions': {
            'series': {
                'point': {
                    'events': {
                        'click': 'click_function'
                    }
                },
            }
        },
        'series': [],
        'title': {
            'text': None
        },
        'xAxis': {
            'categories': checkpoints,
            'title': {
                'text': 'Injected Checkpoint'
            }
        },
        'yAxis': {
            'labels': {
                'format': '{value}%'
            },
            'max': 100,
            'title': {
                'text': 'Average Data Diff'
            }
        }
    }
    data = injections.values_list(
        'checkpoint').distinct().order_by('checkpoint').annotate(
            avg=Avg(Case(When(result__data_diff__isnull=True, then=0),
                         default='result__data_diff'))
        ).values_list('avg', flat=True)
    chart['series'].append({'data': [x*100 if x is not None else 0
                                     for x in data]})
    chart = dumps(chart, indent=4).replace('\"click_function\"', """
    function(event) {
        window.location.assign('results?injection__checkpoint='+this.category);
    }
    """.replace('\n    ', '\n                        '))
    chart_data.append(chart)
    chart_list.append(('diff_checkpoints_chart', 'Data Diff Over Time', False,
                       order))
    print('diff_checkpoints_chart:', round(time()-start, 2), 'seconds')