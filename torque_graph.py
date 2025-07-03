import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QLineEdit, QPushButton, QHBoxLayout, QMessageBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class TorqueGraphApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Torque Curve Visualizer")
        self.setGeometry(100, 100, 800, 600)

        # Layouts
        main_layout = QVBoxLayout()
        input_layout = QHBoxLayout()

        # Input fields
        self.p1_input = QLineEdit()
        self.p2_input = QLineEdit()
        self.tadj_input = QLineEdit()

        input_layout.addWidget(QLabel("Torque coefficient 1:"))
        input_layout.addWidget(self.p1_input)
        input_layout.addWidget(QLabel("Torque coefficient 2:"))
        input_layout.addWidget(self.p2_input)
        input_layout.addWidget(QLabel("Torque adjustment:"))
        input_layout.addWidget(self.tadj_input)

        # Plot button
        self.plot_button = QPushButton("Plot Torque Curve")
        self.plot_button.clicked.connect(self.plot_graph)

        # Matplotlib canvas
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)

        # Label to show hover coordinates
        self.coord_label = QLabel("Hover over graph to see RPM and Torque")
        main_layout.addWidget(self.coord_label)

        # Connect motion event to handler
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)


        # Assemble layout
        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.plot_button)
        main_layout.addWidget(self.canvas)
        self.setLayout(main_layout)

    def torque_function(self, R, P1, P2, T_adj):
        term1 = (P1 * R) / 256
        term2 = ((P2 * R) / 65536) * (R / 256)
        return (term1 - term2) * R + T_adj

    def on_mouse_move(self, event):
        if event.inaxes:  # Only respond if inside axes
            rpm_val = event.xdata
            torque_val = event.ydata
            if rpm_val is not None and torque_val is not None:
                self.coord_label.setText(f"In-Game RPM: {rpm_val:.0f}, Torque: {torque_val:.0f}")
        else:
            self.coord_label.setText("Hover over graph to see RPM and Torque")


    def plot_graph(self):
        try:
            P1 = float(self.p1_input.text())
            P2 = float(self.p2_input.text())
            T_adj = float(self.tadj_input.text())
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numeric values.")
            return

        # RPM range (simulation units)
        rpm = np.linspace(0, 7500, 500)

        user_torque = np.maximum(self.torque_function(rpm, P1, P2, T_adj), 0)
        ref_torque = np.maximum(self.torque_function(rpm, 1290, 8675, 0), 0)


        # Display: multiply x-axis by 2 for in-game RPM units
        rpm_display = rpm * 2

        # Plotting
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(rpm_display, user_torque, label="User-defined Torque", color='blue')
        ax.plot(rpm_display, ref_torque, label="Reference Torque (1290, 8675, 0)", color='red', linestyle='--')
        ax.set_title("Engine Torque vs In-Game RPM")
        ax.set_xlabel("In-Game RPM")
        ax.set_ylabel("Torque (arbitrary units)")
        ax.grid(True)
        ax.legend()
        self.canvas.draw()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TorqueGraphApp()
    window.show()
    sys.exit(app.exec_())
