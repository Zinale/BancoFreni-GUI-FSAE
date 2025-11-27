"""
Applicazione GUI per visualizzare dati dal sensore di pressione freni
Legge dati dalla Feather M4 CAN via seriale e li visualizza in tempo reale
"""
import os
import sys
import json
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QFileDialog, QMessageBox, QGroupBox, QDialog,
                             QListWidget, QDialogButtonBox, QVBoxLayout as QVBoxLayoutDialog)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
import pyqtgraph as pg
import serial
import serial.tools.list_ports
import time


class FileListDialog(QDialog):
    """Dialog per selezionare un file dalla lista"""
    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleziona Stint da Caricare")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayoutDialog()
        
        layout.addWidget(QLabel("File disponibili sulla Feather:"))
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(files)
        layout.addWidget(self.list_widget)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_selected_file(self):
        item = self.list_widget.currentItem()
        if item:
            text = item.text()
            # Formato: "- nome_file.json (1234 bytes)"
            if text.startswith('- '):
                text = text[2:]
            # Rimuovi la parte " (XXX bytes)"
            if ' (' in text:
                filename = text.split(' (')[0]
            else:
                filename = text
            return filename.strip()
        return None


class SerialReader(QThread):
    """Thread per leggere i dati dalla porta seriale"""
    data_received = pyqtSignal(float, str)  # valore, timestamp
    disconnection_error = pyqtSignal(str)  # Segnale per disconnessione improvvisa
    
    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
        self.running = False
        self.paused = False  # Per mettere in pausa la lettura durante i comandi
        
    def run(self):
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            
            while self.running:
                try:
                    if not self.paused and self.serial_connection.in_waiting > 0:
                        line = self.serial_connection.readline().decode('utf-8').strip()
                        try:
                            # Formato atteso: "timestamp,valore"
                            if ',' in line:
                                timestamp, value = line.split(',')
                                self.data_received.emit(float(value), timestamp)
                            else:
                                value = float(line)
                                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                self.data_received.emit(value, timestamp)
                        except ValueError:
                            pass  
                    elif self.paused:
                        time.sleep(0.01)  # Breve pausa se in stato paused
                except (serial.SerialException, OSError) as e:
                    # Porta disconnessa durante la lettura
                    self.running = False
                    self.disconnection_error.emit(f"Porta seriale disconnessa: {str(e)}")
                    break
                        
        except serial.SerialException as e:
            print(f"Errore seriale: {e}")
            self.disconnection_error.emit(f"Impossibile aprire la porta seriale: {str(e)}")
        finally:
            if self.serial_connection and self.serial_connection.is_open:
                try:
                    self.serial_connection.close()
                except:
                    pass
    
    def stop(self):
        self.running = False
        self.wait()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitoraggio Pressione Freni - Polimarche Racing Team")
        self.setGeometry(100, 100, 1200, 700)
        
        self.time_data = []
        self.pressure_data = []
        self.stint_data = []  # Per salvare i dati dello stint corrente
        self.serial_reader = None
        self.stint_active = False
        self.data_frozen = False  # Flag per bloccare l'acquisizione
        
        self.setup_ui()
        
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "src/logo.ico")
        self.setWindowIcon(QIcon(icon_path))
        
        
        self.update_serial_ports()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        controls_group = QGroupBox("Controlli")
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Porta:"))
        self.port_combo = QComboBox()
        controls_layout.addWidget(self.port_combo)
        
        self.refresh_btn = QPushButton("Aggiorna")
        self.refresh_btn.setMaximumWidth(80)
        self.refresh_btn.clicked.connect(self.update_serial_ports)
        controls_layout.addWidget(self.refresh_btn)
        
        self.connect_btn = QPushButton("Connetti")
        self.connect_btn.clicked.connect(self.toggle_connection)
        controls_layout.addWidget(self.connect_btn)
        
        controls_layout.addStretch()
        
        self.start_stint_btn = QPushButton("Inizia Stint")
        self.start_stint_btn.clicked.connect(self.start_stint)
        self.start_stint_btn.setEnabled(False)
        controls_layout.addWidget(self.start_stint_btn)
        
        self.stop_stint_btn = QPushButton("Termina Stint")
        self.stop_stint_btn.clicked.connect(self.stop_stint)
        self.stop_stint_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_stint_btn)
        
        self.save_to_sd_btn = QPushButton("Salva su Flash")     #Feather M4 CAN 
        self.save_to_sd_btn.clicked.connect(self.save_stint_to_sd)
        self.save_to_sd_btn.setEnabled(False)
        controls_layout.addWidget(self.save_to_sd_btn)
        
        self.load_from_sd_btn = QPushButton("Carica da Flash")
        self.load_from_sd_btn.clicked.connect(self.load_stint_from_sd)
        self.load_from_sd_btn.setEnabled(False)
        controls_layout.addWidget(self.load_from_sd_btn)
        
        self.export_csv_btn = QPushButton("Esporta CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        self.export_csv_btn.setEnabled(False)
        controls_layout.addWidget(self.export_csv_btn)
        
        self.freeze_btn = QPushButton("Sblocca Grafico")
        self.freeze_btn.clicked.connect(self.toggle_freeze)
        self.freeze_btn.setEnabled(False)
        controls_layout.addWidget(self.freeze_btn)
        
        self.manage_flash_btn = QPushButton("Gestisci Memoria")
        self.manage_flash_btn.clicked.connect(self.manage_flash_storage)
        self.manage_flash_btn.setEnabled(False)
        controls_layout.addWidget(self.manage_flash_btn)
        
        controls_group.setLayout(controls_layout)
        main_layout.addWidget(controls_group)
        
        values_group = QGroupBox("Valori Attuali")
        values_layout = QHBoxLayout()
        
        self.current_value_label = QLabel("-- bar")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        self.current_value_label.setFont(font)
        values_layout.addWidget(QLabel("Pressione:"))
        values_layout.addWidget(self.current_value_label)
        
        values_layout.addStretch()
        
        self.min_value_label = QLabel("Min: --")
        self.max_value_label = QLabel("Max: --")
        self.avg_value_label = QLabel("Media: --")
        values_layout.addWidget(self.min_value_label)
        values_layout.addWidget(self.max_value_label)
        values_layout.addWidget(self.avg_value_label)
        
        values_group.setLayout(values_layout)
        main_layout.addWidget(values_group)
        
        # Grafico
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle("Pressione Freni nel Tempo", color="k", size="14pt")
        self.plot_widget.setLabel('left', 'Pressione (bar)', color='k')
        self.plot_widget.setLabel('bottom', 'Tempo (s)', color='k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()
        
        # Curva dati
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='b', width=2), name="Pressione")
        
        main_layout.addWidget(self.plot_widget)
        
        # Status bar
        self.statusBar().showMessage("Pronto")
        
    def update_serial_ports(self):
        """Aggiorna la lista delle porte seriali disponibili"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")
            
    def toggle_connection(self):
        """Connetti/disconnetti dalla porta seriale"""
        if self.serial_reader is None or not self.serial_reader.running:
            # Connetti
            port_text = self.port_combo.currentText()
            if not port_text:
                QMessageBox.warning(self, "Errore", "Seleziona una porta seriale")
                return
                
            port = port_text.split(' - ')[0]
            
            self.serial_reader = SerialReader(port)
            self.serial_reader.data_received.connect(self.on_data_received)
            self.serial_reader.disconnection_error.connect(self.on_disconnection_error)
            self.serial_reader.start()
            
            self.connect_btn.setText("Disconnetti")
            self.start_stint_btn.setEnabled(True)
            self.load_from_sd_btn.setEnabled(True)
            self.manage_flash_btn.setEnabled(True)
            self.statusBar().showMessage(f"Connesso a {port}")
        else:
            # Disconnetti
            if self.stint_active:
                reply = QMessageBox.question(self, "Stint Attivo", 
                                            "Uno stint è in corso. Terminarlo prima di disconnettere?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.stop_stint()
                    
            self.serial_reader.stop()
            self.serial_reader = None
            
            self.connect_btn.setText("Connetti")
            self.start_stint_btn.setEnabled(False)
            self.stop_stint_btn.setEnabled(False)
            self.save_to_sd_btn.setEnabled(False)
            self.load_from_sd_btn.setEnabled(False)
            self.manage_flash_btn.setEnabled(False)
            self.statusBar().showMessage("Disconnesso")
            
    def on_disconnection_error(self, error_message):
        """Gestisce la disconnessione improvvisa della porta seriale"""
        # Ferma lo stint se attivo
        if self.stint_active:
            self.stint_active = False
        
        # Reset interfaccia
        self.reset_ui()
        
        # Mostra messaggio all'utente
        QMessageBox.warning(self, "Disconnessione", 
                           f"La porta seriale si è disconnessa!\n\n{error_message}\n\nL'interfaccia è stata resettata.")
        
        self.statusBar().showMessage("Disconnesso - Porta seriale rimossa")
    
    def reset_ui(self):
        """Resetta l'interfaccia dopo una disconnessione"""
        # Ferma il thread se ancora in esecuzione
        if self.serial_reader:
            self.serial_reader.running = False
            self.serial_reader = None
        
        # Reset pulsanti
        self.connect_btn.setText("Connetti")
        self.start_stint_btn.setEnabled(False)
        self.stop_stint_btn.setEnabled(False)
        self.save_to_sd_btn.setEnabled(False)
        self.load_from_sd_btn.setEnabled(False)
        self.manage_flash_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)
        self.freeze_btn.setEnabled(False)
        
        # Reset dati se stint non salvato
        if self.stint_active:
            self.time_data = []
            self.pressure_data = []
            self.stint_data = []
            self.curve.setData([], [])
        
        # Reset flag
        self.stint_active = False
        self.data_frozen = False
        
        # Reset valori visualizzati
        self.current_value_label.setText("-- bar")
        self.min_value_label.setText("Min: --")
        self.max_value_label.setText("Max: --")
        self.avg_value_label.setText("Media: --")
    
    def on_data_received(self, value, timestamp):
        """Callback quando arrivano nuovi dati"""
        if self.data_frozen:
            return
            
        if len(self.time_data) == 0:
            self.time_data.append(0)
        else:
            # Incrementa di 0.1s (100ms)
            self.time_data.append(self.time_data[-1] + 0.1)
            
        self.pressure_data.append(value)
        
        # Se stint attivo, salva i dati
        if self.stint_active:
            self.stint_data.append({
                'timestamp': timestamp,
                'time': self.time_data[-1],
                'pressure': value
            })
        
        # Limita a ultimi 1000 valori per performance --> salva l'ultimo 1 minuto e 40 secondi a 10Hz
        if len(self.time_data) > 1000:
            self.time_data = self.time_data[-1000:]
            self.pressure_data = self.pressure_data[-1000:]
        
        # Aggiorna grafico
        self.curve.setData(self.time_data, self.pressure_data)
        
        # Aggiorna valori
        self.current_value_label.setText(f"{value:.2f} bar")
        
        if len(self.pressure_data) > 0:
            self.min_value_label.setText(f"Min: {min(self.pressure_data):.2f} bar")
            self.max_value_label.setText(f"Max: {max(self.pressure_data):.2f} bar")
            self.avg_value_label.setText(f"Media: {sum(self.pressure_data)/len(self.pressure_data):.2f} bar")
            
    def start_stint(self):
        """Inizia un nuovo stint"""
        self.stint_active = True
        self.stint_data = []
        self.time_data = []
        self.pressure_data = []
        
        self.start_stint_btn.setEnabled(False)
        self.stop_stint_btn.setEnabled(True)
        self.statusBar().showMessage("Stint in corso...")
        
    def stop_stint(self):
        """Termina lo stint corrente"""
        self.stint_active = False
        self.start_stint_btn.setEnabled(True)
        self.stop_stint_btn.setEnabled(False)
        self.save_to_sd_btn.setEnabled(True)
        
        stint_duration = self.time_data[-1] if self.time_data else 0
        self.statusBar().showMessage(f"Stint terminato - Durata: {stint_duration:.1f}s - {len(self.stint_data)} campioni")
        
    def save_stint_to_sd(self):
        """Salva lo stint sulla memoria flash della Feather"""
        if not self.stint_data:
            QMessageBox.warning(self, "Errore", "Nessun dato da salvare")
            return
            
        # Genera nome file con timestamp
        filename = datetime.now().strftime("stint_%Y%m%d_%H%M%S.json")
        
        # Prepara i dati
        stint_info = {
            'date': datetime.now().isoformat(),
            'duration': self.time_data[-1] if self.time_data else 0,
            'samples': len(self.stint_data),
            'data': self.stint_data
        }
        
        # Invia comando alla Feather per salvare su flash
        if self.serial_reader and self.serial_reader.serial_connection:
            try:
                # Verifica che la connessione sia ancora attiva
                if not self.serial_reader.serial_connection.is_open:
                    QMessageBox.warning(self, "Errore", "Porta seriale disconnessa")
                    self.reset_ui()
                    return
                    
                self.statusBar().showMessage("Invio stint alla Feather...")
                
                # Metti in pausa la lettura continua
                self.serial_reader.paused = True
                time.sleep(0.1)
                
                # Pulisci buffer
                self.serial_reader.serial_connection.reset_input_buffer()
                
                # Formato: SAVE:filename:json_data
                command = f"SAVE:{filename}:{json.dumps(stint_info)}\n"
                self.serial_reader.serial_connection.write(command.encode())
                
                # Attendi risposta
                time.sleep(0.5)
                
                response = ""
                timeout = time.time() + 3
                while time.time() < timeout:
                    if self.serial_reader.serial_connection.in_waiting > 0:
                        line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                        if line.startswith("OK:") or line.startswith("ERROR:"):
                            response = line
                            break
                    else:
                        time.sleep(0.1)
                
                # Riprendi lettura continua
                self.serial_reader.paused = False
                
                if response.startswith("OK:"):
                    QMessageBox.information(self, "Successo", f"Stint salvato su memoria flash!\n\n{response[3:]}")
                    self.save_to_sd_btn.setEnabled(False)
                    self.statusBar().showMessage(f"Stint salvato: {filename}")
                elif response.startswith("ERROR:"):
                    QMessageBox.critical(self, "Errore", f"Errore dalla Feather:\n{response[6:]}")
                    self.statusBar().showMessage("Errore nel salvataggio")
                else:
                    QMessageBox.warning(self, "Timeout", "Nessuna risposta dalla Feather. Il file potrebbe essere stato salvato comunque.")
                    self.statusBar().showMessage("Timeout - verifica con 'Carica da Flash'")
                    
            except (serial.SerialException, OSError) as e:
                self.serial_reader.paused = False
                QMessageBox.critical(self, "Errore", f"Porta seriale disconnessa durante l'operazione: {str(e)}")
                self.reset_ui()
            except Exception as e:
                self.serial_reader.paused = False
                QMessageBox.critical(self, "Errore", f"Impossibile salvare su flash: {str(e)}")
                
    def load_stint_from_sd(self):
        """Carica uno stint dalla memoria flash della Feather"""
        if not self.serial_reader or not self.serial_reader.serial_connection:
            QMessageBox.warning(self, "Errore", "Nessuna connessione seriale attiva")
            return
        
        # Verifica che la connessione sia ancora attiva
        if not self.serial_reader.serial_connection.is_open:
            QMessageBox.warning(self, "Errore", "Porta seriale disconnessa")
            self.reset_ui()
            return
            
        try:
            self.statusBar().showMessage("Richiesta lista file dalla Feather...")
            
            # Metti in pausa la lettura 
            self.serial_reader.paused = True
            time.sleep(0.1)
            
            self.serial_reader.serial_connection.reset_input_buffer()
            self.serial_reader.serial_connection.write(b"LIST\n")
            
            time.sleep(0.5)  
            
            files = []
            reading_files = False
            
            while self.serial_reader.serial_connection.in_waiting > 0:
                line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                
                if line == "FILES:":
                    reading_files = True
                    continue
                elif line == "END_FILES":
                    reading_files = False
                    break
                elif line.startswith("ERROR:"):
                    QMessageBox.critical(self, "Errore", f"Errore dalla Feather: {line}")
                    return
                elif reading_files and line.startswith("-"):
                    files.append(line)
            
            if not files:
                self.serial_reader.paused = False
                QMessageBox.information(self, "Nessun File", "Nessuno stint salvato sulla Feather")
                return
            
            # Mostra dialog per selezionare il file
            dialog = FileListDialog(files, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_file = dialog.get_selected_file()
                
                if selected_file:
                    self.statusBar().showMessage(f"Caricamento {selected_file}...")
                    
                    self.serial_reader.serial_connection.reset_input_buffer()
                    
                    # Richiedi il file
                    command = f"LOAD:{selected_file}\n"
                    print(f"DEBUG: Invio comando: {command.strip()}")  # Debug
                    self.serial_reader.serial_connection.write(command.encode())
                    
                    time.sleep(0.5)
                    
                    data_content = ""
                    reading_data = False
                    
                    timeout = time.time() + 5  # Timeout 
                    while time.time() < timeout:
                        if self.serial_reader.serial_connection.in_waiting > 0:
                            line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                            
                            if line == "DATA_START":
                                reading_data = True
                                continue
                            elif line == "DATA_END":
                                break
                            elif line.startswith("ERROR:"):
                                QMessageBox.critical(self, "Errore", f"Errore dalla Feather: {line}")
                                return
                            elif reading_data:
                                data_content += line
                        else:
                            time.sleep(0.1)
                    
                    if data_content:
                        # Parsa il JSON
                        stint_info = json.loads(data_content)
                        
                        self.time_data = [d['time'] for d in stint_info['data']]
                        self.pressure_data = [d['pressure'] for d in stint_info['data']]
                        
                        self.curve.setData(self.time_data, self.pressure_data)
                        
                        if self.pressure_data:
                            self.current_value_label.setText(f"{self.pressure_data[-1]:.2f} bar")
                            self.min_value_label.setText(f"Min: {min(self.pressure_data):.2f} bar")
                            self.max_value_label.setText(f"Max: {max(self.pressure_data):.2f} bar")
                            self.avg_value_label.setText(f"Media: {sum(self.pressure_data)/len(self.pressure_data):.2f} bar")
                        
                        self.statusBar().showMessage(f"Stint caricato: {stint_info['samples']} campioni - Durata: {stint_info['duration']:.1f}s")
                        QMessageBox.information(self, "Successo", f"Stint caricato con successo!\n\nCampioni: {stint_info['samples']}\nDurata: {stint_info['duration']:.1f}s")
                        
                        # Blocca il grafico e abilita esportazione CSV
                        self.data_frozen = True
                        self.export_csv_btn.setEnabled(True)
                        self.freeze_btn.setEnabled(True)
                        self.freeze_btn.setText("Sblocca Grafico")
                    else:
                        QMessageBox.warning(self, "Errore", "Nessun dato ricevuto dalla Feather")
                
                # Riprendi lettura continua
                self.serial_reader.paused = False
                        
        except json.JSONDecodeError as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Errore nel parsing JSON: {str(e)}")
        except (serial.SerialException, OSError) as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Porta seriale disconnessa durante l'operazione: {str(e)}")
            self.reset_ui()
        except Exception as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Impossibile caricare da flash: {str(e)}")
    
    def toggle_freeze(self):
        """Blocca/sblocca l'acquisizione dati"""
        self.data_frozen = not self.data_frozen
        
        if self.data_frozen:
            self.freeze_btn.setText("Sblocca Grafico")
            self.export_csv_btn.setEnabled(True)
            self.statusBar().showMessage("Grafico bloccato - Dati congelati")
        else:
            self.freeze_btn.setText("Blocca Grafico")
            self.export_csv_btn.setEnabled(False)
            self.statusBar().showMessage("Grafico sbloccato - Acquisizione attiva")
    
    def export_to_csv(self):
        """Esporta i dati correnti in formato CSV"""
        if not self.time_data or not self.pressure_data:
            QMessageBox.warning(self, "Errore", "Nessun dato da esportare")
            return
        
        try:
            # Genera nome file con timestamp
            filename = datetime.now().strftime("stint_export_%Y%m%d_%H%M%S.csv")
            
            # Scrivi il CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                csvfile.write("Tempo (s),Pressione (bar)\n")
                for t, p in zip(self.time_data, self.pressure_data):
                    csvfile.write(f"{t:.2f},{p:.2f}\n")
            
            QMessageBox.information(self, "Successo", 
                                  f"Dati esportati con successo!\n\nFile: {filename}\nCampioni: {len(self.time_data)}")
            self.statusBar().showMessage(f"Esportato: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile esportare CSV: {str(e)}")
    
    def manage_flash_storage(self):
        """Gestisce la memoria flash: mostra info, elimina file, formatta"""
        if not self.serial_reader or not self.serial_reader.serial_connection:
            QMessageBox.warning(self, "Errore", "Nessuna connessione seriale attiva")
            return
        
        # Verifica che la connessione sia ancora attiva
        if not self.serial_reader.serial_connection.is_open:
            QMessageBox.warning(self, "Errore", "Porta seriale disconnessa")
            self.reset_ui()
            return
        
        try:
            # Richiedi informazioni sulla memoria
            self.serial_reader.paused = True
            time.sleep(0.1)
            
            self.serial_reader.serial_connection.reset_input_buffer()
            self.serial_reader.serial_connection.write(b"INFO\n")
            
            time.sleep(0.3)
            
            total_size = 0
            used_space = 0
            file_count = 0
            reading_info = False
            
            while self.serial_reader.serial_connection.in_waiting > 0:
                line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                
                if line == "INFO_START":
                    reading_info = True
                    continue
                elif line == "INFO_END":
                    break
                elif reading_info:
                    if line.startswith("Total: "):
                        total_size = int(line.split(": ")[1])
                    elif line.startswith("Used: "):
                        used_space = int(line.split(": ")[1])
                    elif line.startswith("Files: "):
                        file_count = int(line.split(": ")[1])
            
            free_space = total_size - used_space
            usage_percent = (used_space / total_size * 100) if total_size > 0 else 0
            
            # Crea dialog personalizzato
            dialog = QDialog(self)
            dialog.setWindowTitle("Gestione Memoria Flash")
            dialog.setMinimumWidth(500)
            
            layout = QVBoxLayout()
            
            # Info memoria
            info_text = f"""Informazioni Memoria Flash:

Spazio totale: {total_size / 1024:.1f} KB ({total_size / (1024*1024):.2f} MB)
Spazio usato: {used_space / 1024:.1f} KB ({usage_percent:.1f}%)
Spazio libero: {free_space / 1024:.1f} KB
File salvati: {file_count}"""
            
            info_label = QLabel(info_text)
            layout.addWidget(info_label)
            
            # Pulsanti azione
            btn_layout = QHBoxLayout()
            
            delete_btn = QPushButton("Elimina File Selezionati")
            delete_btn.clicked.connect(lambda: self.delete_selected_stints(dialog))
            btn_layout.addWidget(delete_btn)
            
            format_btn = QPushButton("Formatta (Elimina Tutto)")
            format_btn.clicked.connect(lambda: self.format_flash(dialog))
            btn_layout.addWidget(format_btn)
            
            close_btn = QPushButton("Chiudi")
            close_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            dialog.setLayout(layout)
            
            self.serial_reader.paused = False
            dialog.exec()
            
        except (serial.SerialException, OSError) as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Porta seriale disconnessa durante l'operazione: {str(e)}")
            self.reset_ui()
        except Exception as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Impossibile ottenere info memoria: {str(e)}")
    
    def delete_selected_stints(self, parent_dialog):
        """Mostra lista file e permette eliminazione selettiva"""
        try:
            self.serial_reader.paused = True
            time.sleep(0.1)
            
            self.serial_reader.serial_connection.reset_input_buffer()
            self.serial_reader.serial_connection.write(b"LIST\n")
            
            time.sleep(0.5)
            
            files = []
            reading_files = False
            
            while self.serial_reader.serial_connection.in_waiting > 0:
                line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                
                if line == "FILES:":
                    reading_files = True
                    continue
                elif line == "END_FILES":
                    break
                elif reading_files and line.startswith("-"):
                    files.append(line)
            
            if not files:
                self.serial_reader.paused = False
                QMessageBox.information(self, "Info", "Nessun file da eliminare")
                return
            
            # Dialog per selezione multipla
            delete_dialog = QDialog(parent_dialog)
            delete_dialog.setWindowTitle("Seleziona File da Eliminare")
            delete_dialog.setMinimumWidth(450)
            
            layout = QVBoxLayoutDialog()
            layout.addWidget(QLabel("Seleziona i file da eliminare (Ctrl+Click per selezione multipla):"))
            
            list_widget = QListWidget()
            list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            list_widget.addItems(files)
            layout.addWidget(list_widget)
            
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(delete_dialog.accept)
            buttons.rejected.connect(delete_dialog.reject)
            layout.addWidget(buttons)
            
            delete_dialog.setLayout(layout)
            
            if delete_dialog.exec() == QDialog.DialogCode.Accepted:
                selected_items = list_widget.selectedItems()
                
                if not selected_items:
                    self.serial_reader.paused = False
                    return
                
                # Conferma eliminazione
                reply = QMessageBox.question(self, "Conferma", 
                                            f"Eliminare {len(selected_items)} file?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    deleted_count = 0
                    
                    for item in selected_items:
                        text = item.text()
                        if text.startswith('- '):
                            text = text[2:]
                        if ' (' in text:
                            filename = text.split(' (')[0].strip()
                        else:
                            filename = text.strip()
                        
                        # Invia comando DELETE
                        self.serial_reader.serial_connection.reset_input_buffer()
                        command = f"DELETE:{filename}\n"
                        self.serial_reader.serial_connection.write(command.encode())
                        
                        time.sleep(0.2)
                        
                        # Leggi risposta
                        if self.serial_reader.serial_connection.in_waiting > 0:
                            response = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                            if response.startswith("OK:"):
                                deleted_count += 1
                    
                    QMessageBox.information(self, "Successo", f"{deleted_count} file eliminati")
                    parent_dialog.accept()  # Chiudi il dialog di gestione per aggiornare
            
            self.serial_reader.paused = False
            
        except Exception as e:
            self.serial_reader.paused = False
            QMessageBox.critical(self, "Errore", f"Errore durante eliminazione: {str(e)}")
    
    def format_flash(self, parent_dialog):
        """Formatta completamente la memoria flash (elimina tutti gli stint)"""
        reply = QMessageBox.warning(self, "ATTENZIONE", 
                                   "Questa operazione eliminerà TUTTI gli stint salvati sulla Feather!\n\nSei sicuro?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.serial_reader.paused = True
                time.sleep(0.1)
                
                self.serial_reader.serial_connection.reset_input_buffer()
                self.serial_reader.serial_connection.write(b"FORMAT\n")
                
                time.sleep(1)  # Attendi più tempo per la formattazione
                
                response = ""
                timeout = time.time() + 5
                while time.time() < timeout:
                    if self.serial_reader.serial_connection.in_waiting > 0:
                        line = self.serial_reader.serial_connection.readline().decode('utf-8').strip()
                        if line.startswith("OK:"):
                            response = line
                            break
                    else:
                        time.sleep(0.1)
                
                self.serial_reader.paused = False
                
                if response.startswith("OK:"):
                    QMessageBox.information(self, "Successo", f"Memoria formattata!\n\n{response[3:]}")
                    parent_dialog.accept()
                else:
                    QMessageBox.warning(self, "Timeout", "Nessuna risposta dalla Feather")
                    
            except Exception as e:
                self.serial_reader.paused = False
                QMessageBox.critical(self, "Errore", f"Errore durante formattazione: {str(e)}")
                
    def closeEvent(self, event):
        """Gestisce la chiusura dell'applicazione"""
        if self.serial_reader and self.serial_reader.running:
            self.serial_reader.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
