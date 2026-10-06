"""Live engine curve editor; graph values are in arbitrary simulation units."""
import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QFormLayout)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class TorqueGraphApp(QWidget):
    FIELDS = (
        ('torque_coefficient_1', 'Torque coefficient 1'),
        ('torque_coefficient_2', 'Torque coefficient 2'),
        ('torque_adjustment', 'Torque adjustment'),
        ('rpm_upshift_point', 'Upshift RPM (in game)'),
        ('rpm_downshift_point', 'Downshift RPM (in game)'),
        ('rpm_limit', 'RPM limit (in game)'),
    )

    def __init__(self, model=None):
        super().__init__()
        self.model = model
        self._subscribed = model is not None
        self.setWindowTitle('Engine Torque Curve')
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        self.engine = QComboBox()
        for name in ('Ford', 'Mercedes', 'Honda'):
            if model is None or all('engine.' + name.lower() + '.' + field in model.parameters
                                    for field, _ in self.FIELDS):
                self.engine.addItem(name)
        layout.addWidget(self.engine)
        form = QFormLayout()
        self.inputs = {}
        for field, label in self.FIELDS:
            control = QDoubleSpinBox() if field == "torque_adjustment" else QSpinBox()
            if field == "torque_adjustment":
                control.setDecimals(0)
            control.setRange(0, 4294967295 if field == "torque_adjustment" else 2147483647)
            self.inputs[field] = control
            form.addRow(label, control)
            control.valueChanged.connect(lambda value, f=field: self.edit_value(f, value))
        layout.addLayout(form)
        self.coord_label = QLabel('Torque is shown in arbitrary units; this is the existing curve model.')
        layout.addWidget(self.coord_label)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.engine.currentIndexChanged.connect(self.refresh)
        if model is not None:
            model.subscribe(self.on_model_change)
        else:
            for (field, _), value in zip(self.FIELDS, (1290, 8675, 0, 13000, 7800, 13000)):
                self.inputs[field].blockSignals(True)
                self.inputs[field].setValue(value)
                self.inputs[field].blockSignals(False)
        self.refresh()

    def parameter_id(self, field):
        return 'engine.' + self.engine.currentText().lower() + '.' + field

    def edit_value(self, field, value):
        if self.model is not None:
            self.model.set_value(self.parameter_id(field), value // 2 if field.startswith('rpm_') else int(value))
            self.refresh()  # Display the representable RPM after rounding.
        else:
            self.plot_graph()

    def on_model_change(self, pid):
        if pid.startswith('engine.' + self.engine.currentText().lower() + '.'):
            self.refresh()

    def refresh(self, *_):
        available = self.engine.count() > 0
        for field, control in self.inputs.items():
            control.setEnabled(available)
            if self.model is not None and available:
                param = self.model.parameters[self.parameter_id(field)]
                scale = 2 if field.startswith('rpm_') else 1
                maximum = ((1 << (int(param['Length']) * 8)) - 1) * scale
                control.blockSignals(True)
                control.setMaximum(maximum)
                control.setSingleStep(scale)
                control.setValue(self.model.get_value(self.parameter_id(field)) * scale)
                control.blockSignals(False)
        if available:
            self.plot_graph()
        else:
            self.coord_label.setText('No complete engine parameter set is available for this executable.')

    @staticmethod
    def torque_function(R, P1, P2, T_adj):
        return ((P1 * R) / 256 - ((P2 * R) / 65536) * (R / 256)) * R + T_adj

    def plot_graph(self):
        rpm = np.linspace(0, 7500, 500)
        fields = ('torque_coefficient_1', 'torque_coefficient_2', 'torque_adjustment')
        current = [self.inputs[f].value() for f in fields]
        if self.model is None:
            stock = [1290, 8675, 0]
        else:
            stock = [float(self.model.parameters[self.parameter_id(f)]['Default value']) for f in fields]
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(rpm * 2, np.maximum(self.torque_function(rpm, *current), 0), label='Current staged values')
        ax.plot(rpm * 2, np.maximum(self.torque_function(rpm, *stock), 0), '--', label='Stock defaults')
        for field, label in self.FIELDS[3:]:
            ax.axvline(self.inputs[field].value(), linestyle=':', label=label)
        ax.set_title(self.engine.currentText() + ' engine torque curve')
        ax.set_xlabel('In-game RPM')
        ax.set_ylabel('Torque (arbitrary units)')
        ax.grid(True)
        ax.legend()
        self.canvas.draw_idle()

    def on_mouse_move(self, event):
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            self.coord_label.setText(f'In-game RPM: {event.xdata:.0f}, Torque: {event.ydata:.0f} (arbitrary units)')

    def closeEvent(self, event):
        if self._subscribed:
            self.model.unsubscribe(self.on_model_change)
            self._subscribed = False
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TorqueGraphApp()
    window.show()
    sys.exit(app.exec_())
