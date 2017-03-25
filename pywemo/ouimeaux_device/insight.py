import logging
from datetime import datetime
from .switch import Switch

LOG = logging.getLogger(__name__)


class Insight(Switch):
    def __init__(self, *args, **kwargs):
        Switch.__init__(self, *args, **kwargs)
        self.insight_params = {}

    def __repr__(self):
        return '<WeMo Insight "{name}">'.format(name=self.name)

    def update_insight_params(self):
        params = self.insight.GetInsightParams().get('InsightParams')
        self.insight_params = self.parse_insight_params(params)

    def subscription_update(self, _type, _params):
        LOG.debug("subscription_update %s %s", _type, _params)
        if _type == "InsightParams":
            self.insight_params = self.parse_insight_params(_params)
            return True
        return Switch.subscription_update(self, _type, _params)

    def parse_insight_params(self, params):
        (
            state,  # 0 if off, 1 if on, 8 if on but load is off
            lastchange,
            onfor,  # seconds
            ontoday,  # seconds
            ontotal,  # seconds
            timeperiod,  # The period over which averages are calculated
            _x,  # This one is always 19 for me; what is it?
            currentmw,
            todaymw,
            totalmw,
            powerthreshold
        ) = params.split('|')
        return {'state': state,
                'lastchange': datetime.fromtimestamp(int(lastchange)),
                'onfor': int(onfor),
                'ontoday': int(ontoday),
                'ontotal': int(ontotal),
                'todaymw': int(float(todaymw)),
                'totalmw': int(float(totalmw)),
                'currentpower': int(float(currentmw)),
                'powerthreshold': int(float(powerthreshold))}

    def get_state(self, force_update=False):
        if force_update or self._state is None:
            self.update_insight_params()

        return Switch.get_state(self, force_update)

    @property
    def today_kwh(self):
        return self.insight_params['todaymw'] * 1.6666667e-8

    @property
    def current_power(self):
        """
        Returns the current power usage in mW.
        """
        return self.insight_params['currentpower']

    @property
    def threshold_power(self):
        """
        Returns the threshold power. Above this the device is on, below it is standby.
        """
        return self.insight_params['powerthreshold']

    @property
    def today_on_time(self):
        return self.insight_params['ontoday']

    @property
    def on_for(self):
        return self.insight_params['onfor']

    @property
    def last_change(self):
        return self.insight_params['lastchange']

    @property
    def today_standby_time(self):
        return self.insight_params['ontoday']

    @property
    def get_standby_state(self):
        state = self.insight_params['state']
        if state == '0':
            return 'off'
        if state == '1':
            return 'on'
        else:
            return 'standby'
