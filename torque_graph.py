"""Live engine curve editor; graph values are in arbitrary simulation units."""
import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QFormLayout, QSlider, QHBoxLayout)
from PyQt5.QtCore import Qt, QTimer
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
        ('fuel_consumption_rate', 'Fuel consumption rate'),
        ('durability_coefficient', 'Durability coefficient'),
    )

    def __init__(self, model=None):
        super().__init__()
        self.model = model
        self._subscribed = model is not None
        self.plot_timer = QTimer(self)
        self.plot_timer.setSingleShot(True)
        self.plot_timer.timeout.connect(self.plot_graph)
        self.sliders = {}
        self.slider_ranges = {}
        self.setWindowTitle('Engine Torque Curve')
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        self.engine = QComboBox()
        layout.addWidget(self.engine)
        form = QFormLayout()
        self.inputs = {}
        for field, label in self.FIELDS:
            control = QDoubleSpinBox() if field == "torque_adjustment" else QSpinBox()
            if field == "torque_adjustment":
                control.setDecimals(0)
            control.setRange(0, 4294967295 if field == "torque_adjustment" else 2147483647)
            self.inputs[field] = control
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1000)
            self.sliders[field] = slider
            row = QHBoxLayout()
            row.addWidget(slider, 3)
            row.addWidget(control, 1)
            form.addRow(label, row)
            slider.valueChanged.connect(lambda value, f=field: self.edit_slider(f, value))
            control.valueChanged.connect(lambda value, f=field: self.edit_value(f, value))
        layout.addLayout(form)
        self.coord_label = QLabel('Open an EXE to edit engine parameters. Changes are staged until Save.')
        self.coord_label.setWordWrap(True)
        layout.addWidget(self.coord_label)
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.engine.currentIndexChanged.connect(self.refresh)
        if model is not None:
            model.subscribe(self.on_model_change)
        self.reload_engines()

    def reload_engines(self):
        previous = self.engine.currentText()
        self.engine.blockSignals(True)
        self.engine.clear()
        required = ('torque_coefficient_1', 'torque_coefficient_2', 'torque_adjustment')
        for name in ('Ford', 'Mercedes', 'Honda'):
            if self.model is None or all('engine.' + name.lower() + '.' + field in self.model.parameters
                                         for field in required):
                self.engine.addItem(name)
        index = self.engine.findText(previous)
        if index >= 0:
            self.engine.setCurrentIndex(index)
        self.engine.blockSignals(False)
        if self.model is None:
            defaults = (1290, 8675, 0, 13000, 7800, 13000, 6290, 18)
            for (field, _), value in zip(self.FIELDS, defaults):
                self.inputs[field].blockSignals(True)
                self.inputs[field].setValue(value)
                self.inputs[field].blockSignals(False)
        self.refresh()

    def edit_slider(self, field, position):
        maximum, scale = self.slider_ranges[field]
        value = round(position * maximum / 1000 / scale) * scale
        self.inputs[field].setValue(value)

    def parameter_id(self, field):
        return 'engine.' + self.engine.currentText().lower() + '.' + field

    def edit_value(self, field, value):
        if self.model is not None:
            self.model.set_value(self.parameter_id(field), value // 2 if field.startswith('rpm_') else int(value))
            self.refresh()  # Display the representable RPM after rounding.
        else:
            self.refresh()

    def on_model_change(self, pid):
        if pid.startswith('engine.' + self.engine.currentText().lower() + '.'):
            self.refresh()

    def refresh(self, *_):
        available = self.engine.count() > 0
        self.engine.setEnabled(available)
        for field, control in self.inputs.items():
            pid = self.parameter_id(field)
            supported = available and (self.model is None or pid in self.model.parameters)
            control.setEnabled(supported)
            slider = self.sliders[field]
            slider.setEnabled(supported)
            if not supported:
                control.blockSignals(True)
                control.setValue(0)
                control.blockSignals(False)
                slider.setToolTip('Not available for this executable version.')
                continue
            scale = 2 if field.startswith('rpm_') else 1
            if self.model is not None:
                param = self.model.parameters[pid]
                maximum = ((1 << (int(param['Length']) * 8)) - 1) * scale
                current = self.model.get_value(pid) * scale
                default = int(param['Default value']) * scale
                control.blockSignals(True)
                control.setMaximum(maximum)
                control.setSingleStep(scale)
                control.setValue(current)
                control.setStyleSheet('background-color: #fff1b8;' if pid in self.model.dirty else '')
                control.setToolTip(param.get('Comments', '') + '\n' + pid)
                control.blockSignals(False)
            else:
                maximum = 4294967295 if field == 'torque_adjustment' else 65535 * scale
                current = control.value()
                default = current
            # Sliders cover a useful tuning range; numeric inputs retain full storage bounds.
            tuning_max = 20000 if field.startswith('rpm_') else (20000000 if field == 'torque_adjustment' else max(default * 2, 100))
            tuning_max = min(maximum, max(tuning_max, current))
            self.slider_ranges[field] = (tuning_max, scale)
            slider.blockSignals(True)
            slider.setValue(round(current * 1000 / tuning_max) if tuning_max else 0)
            slider.setToolTip(f'Slider range: 0–{tuning_max:g}. Use the numeric input for precise values.')
            slider.blockSignals(False)
        if available:
            self.coord_label.setText('Changes are staged until Save. Torque is in arbitrary simulation units.')
            self.plot_timer.start(40)
        else:
            self.plot_timer.stop()
            self.figure.clear()
            self.canvas.draw_idle()
            self.coord_label.setText('Open an EXE to edit engine parameters.')

    @staticmethod
    def torque_function(R, P1, P2, T_adj):
        return ((P1 * R) / 256 - ((P2 * R) / 65536) * (R / 256)) * R + T_adj

    def plot_graph(self):
        if self.engine.count() == 0:
            return
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
        for field, label in self.FIELDS[3:6]:
            if not self.inputs[field].isEnabled():
                continue
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
