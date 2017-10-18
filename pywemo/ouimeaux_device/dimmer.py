from .switch import Switch

class Dimmer(Switch):

    def __repr__(self):
        return '<WeMo Dimmer "{name}">'.format(name=self.name)
