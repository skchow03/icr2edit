"""Friendly chassis controls and body-aero visualizations sharing the editor model."""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QComboBox, QDoubleSpinBox, QSlider, QLabel, QPushButton)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Polygon
from chassis_values import aero_summary


class ChassisPanel(QWidget):
    FIELDS = (
        ('weight', 'Base chassis weight (game units)', 1, 0),
        ('drag', 'Body drag coefficient', 65536, 5),
        ('ratio', 'Body downforce / drag ratio', 100, 2),
        ('rear', 'Rear body downforce (%)', 655.36, 4),
    )

    def __init__(self, model):
        super().__init__()
        self.model = model
        layout = QVBoxLayout(self)
        selectors = QHBoxLayout()
        selectors.addWidget(QLabel('Chassis'))
        self.chassis = QComboBox()
        selectors.addWidget(self.chassis)
        selectors.addWidget(QLabel('Settings'))
        self.mode = QComboBox()
        self.mode.addItem('Road course', 'road_course')
        self.mode.addItem('Speedway', 'speedway')
        selectors.addWidget(self.mode)
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.setToolTip("Reset Lola, Penske, and Reynard, including both road-course and speedway settings. Changes are staged until Save.")
        self.reset_button.clicked.connect(self.reset_defaults)
        selectors.addWidget(self.reset_button)
        layout.addLayout(selectors)
        self.inputs, self.sliders, self.slider_max = {}, {}, {}
        form = QFormLayout()
        for field, label, scale, decimals in self.FIELDS:
            control = QDoubleSpinBox()
            control.setDecimals(decimals)
            control.setRange(0, 65535 / scale)
            control.setSingleStep(1 / scale)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1000)
            row = QHBoxLayout()
            row.addWidget(slider, 3)
            row.addWidget(control, 1)
            form.addRow(label, row)
            self.inputs[field], self.sliders[field] = control, slider
            control.valueChanged.connect(lambda value, f=field: self.edit_value(f, value))
            slider.valueChanged.connect(lambda value, f=field: self.edit_slider(f, value))
        layout.addLayout(form)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.figure = Figure(figsize=(9, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas, 1)
        note = QLabel('Diagram is schematic. Aero comparisons estimate body-only changes at the same speed; '
                      'they exclude wings and tire grip. Weight units have not been calibrated. '
                      'Switching settings selects the values to edit; it does not change the race track type.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.draw_visuals)
        self.chassis.currentIndexChanged.connect(self.refresh)
        self.mode.currentIndexChanged.connect(self.refresh)
        model.subscribe(self.on_model_change)
        self.reload_chassis()

    def parameter_id(self, field):
        prefix = 'chassis.' + self.chassis.currentText().lower() + '.'
        names = {'weight': 'base_chassis_weight', 'rear': 'body_downforce_rear_distribution',
                 'drag': self.mode.currentData() + '_body_drag_coefficient',
                 'ratio': self.mode.currentData() + '_body_downforce_to_drag_ratio'}
        return prefix + names[field]

    def reload_chassis(self):
        previous = self.chassis.currentText()
        self.chassis.blockSignals(True)
        self.chassis.clear()
        for name in ('Lola', 'Penske', 'Reynard'):
            prefix = 'chassis.' + name.lower() + '.'
            required = ('base_chassis_weight', 'body_downforce_rear_distribution',
                        'road_course_body_drag_coefficient', 'speedway_body_drag_coefficient',
                        'road_course_body_downforce_to_drag_ratio', 'speedway_body_downforce_to_drag_ratio')
            if all(prefix + field in self.model.parameters for field in required):
                self.chassis.addItem(name)
        index = self.chassis.findText(previous)
        if index >= 0:
            self.chassis.setCurrentIndex(index)
        self.chassis.blockSignals(False)
        self.refresh()

    def reset_defaults(self):
        fields = ('base_chassis_weight', 'body_downforce_rear_distribution',
                  'road_course_body_drag_coefficient', 'speedway_body_drag_coefficient',
                  'road_course_body_downforce_to_drag_ratio', 'speedway_body_downforce_to_drag_ratio')
        ids = [f"chassis.{chassis}.{field}" for chassis in ("lola", "penske", "reynard")
               for field in fields if f"chassis.{chassis}.{field}" in self.model.parameters]
        self.model.reset_defaults(ids)
        self.refresh()

    def edit_value(self, field, value):
        scale = next(scale for f, _, scale, _ in self.FIELDS if f == field)
        self.model.set_value(self.parameter_id(field), min(65535, max(0, round(value * scale))))
        self.refresh()

    def edit_slider(self, field, position):
        raw = round(position * self.slider_max[field] / 1000)
        self.model.set_value(self.parameter_id(field), raw)
        self.refresh()

    def on_model_change(self, pid):
        if pid.startswith('chassis.' + self.chassis.currentText().lower() + '.'):
            self.refresh()

    def refresh(self, *_):
        available = self.chassis.count() > 0
        self.chassis.setEnabled(available)
        self.mode.setEnabled(available)
        self.reset_button.setEnabled(available)
        for field, _, scale, _ in self.FIELDS:
            control, slider = self.inputs[field], self.sliders[field]
            control.setEnabled(available)
            slider.setEnabled(available)
            if not available:
                continue
            pid = self.parameter_id(field)
            param = self.model.parameters[pid]
            raw = self.model.get_value(pid)
            default = int(param['Default value'])
            maximum = 65535 if field in {'rear', 'drag'} else min(65535, max(default * 2, raw, 100))
            self.slider_max[field] = maximum
            control.blockSignals(True)
            control.setValue(raw / scale)
            control.setToolTip(param.get('Comments', '') + '\n' + pid)
            control.setStyleSheet('background-color: #fff1b8;' if pid in self.model.dirty else '')
            control.blockSignals(False)
            slider.blockSignals(True)
            slider.setValue(round(raw * 1000 / maximum))
            slider.setToolTip(f'Slider range: 0–{maximum / scale:g}. Numeric input retains the full range.')
            slider.blockSignals(False)
        if available:
            self.timer.start(40)
        else:
            self.timer.stop()
            self.summary.setText('Open an EXE to edit chassis parameters.')
            self.figure.clear()
            self.canvas.draw_idle()

    def draw_visuals(self):
        if self.chassis.count() == 0:
            return
        values = {field: self.model.get_value(self.parameter_id(field)) for field, *_ in self.FIELDS}
        stock_drag = int(self.model.parameters[self.parameter_id('drag')]['Default value'])
        stock_ratio = int(self.model.parameters[self.parameter_id('ratio')]['Default value'])
        aero = aero_summary(values['drag'], values['ratio'], values['rear'], stock_drag, stock_ratio)
        stock_weight = int(self.model.parameters[self.parameter_id('weight')]['Default value'])
        self.summary.setText(f"{self.chassis.currentText()} · {self.mode.currentText()} | "
                             f"Weight: {values['weight']} game units ({values['weight'] / stock_weight * 100:.1f}% of stock) | "
                             f"Body downforce split: {aero['front_percent']:.1f}% front / {aero['rear_percent']:.1f}% rear")
        self.figure.clear()
        car, comparison = self.figure.subplots(1, 2)
        car.set_title('Body downforce distribution')
        car.add_patch(Polygon([(-.3, -.8), (.3, -.8), (.35, .5), (.12, 1.2), (-.12, 1.2), (-.35, .5)], color='#5c8ab8'))
        for y in (-.65, .65):
            for x in (-.65, .45):
                car.add_patch(Rectangle((x, y - .2), .2, .4, color='#333333'))
        car.add_patch(Rectangle((-.55, .9), 1.1, .08, color='#333333'))
        car.add_patch(Rectangle((-.55, -.85), 1.1, .08, color='#333333'))
        for y, fraction, label in ((.7, aero['front_percent'], 'Front'), (-.6, aero['rear_percent'], 'Rear')):
            car.annotate('', xy=(.85, y), xytext=(.85 + fraction / 100, y),
                         arrowprops=dict(arrowstyle='->', color='#c66b25', lw=3))
            car.text(-1.3, y, f'{label}\n{fraction:.1f}%', va='center')
        car.set_xlim(-1.5, 2)
        car.set_ylim(-1.2, 1.5)
        car.set_aspect('equal')
        car.axis('off')
        comparison.set_title('Estimated body aero vs stock')
        comparison.bar(['Drag', 'Downforce'], [aero['relative_drag'], aero['relative_downforce']], color=['#647fa3', '#c66b25'])
        comparison.axhline(100, color='#555555', linestyle='--', label='Stock = 100%')
        comparison.set_ylabel('% of stock at the same speed')
        comparison.legend()
        comparison.grid(axis='y', alpha=.25)
        self.canvas.draw_idle()
