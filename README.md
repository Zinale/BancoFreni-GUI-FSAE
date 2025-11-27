# 🏎️ Sistema di Monitoraggio Pressione Freni - Polimarche Racing Team

Sistema completo per acquisizione, visualizzazione e analisi dati del sensore di pressione freni per vetture da competizione. Il progetto integra una **GUI desktop in Python** con una scheda **Adafruit Feather M4 CAN** per acquisizione dati in tempo reale.

---

## 📋 Indice

- [Descrizione](#-descrizione)
- [Componenti Hardware](#-componenti-hardware)
- [Requisiti Software](#-requisiti-software)
- [Installazione](#-installazione)
- [Collegamenti Hardware](#-collegamenti-hardware)
- [Utilizzo](#-utilizzo)
- [Funzionalità](#-funzionalità)
- [Formato Dati](#-formato-dati)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Descrizione

Il sistema permette di:
- **Acquisire** dati dal sensore di pressione freni a 10 Hz (ogni 100ms)
- **Visualizzare** in tempo reale i valori su grafico interattivo
- **Registrare** stint completi con salvataggio su memoria flash
- **Analizzare** dati storici caricandoli dalla memoria
- **Esportare** dati in formato CSV per analisi approfondite

---

## 🔧 Componenti Hardware

### Sensore di Pressione
- **Tipo**: Sensore ratiometrico 0-170 bar
- **Range tensione**: 0.5V - 4.5V @ 5V alimentazione (0.33V - 2.97V @ 3.3V)
- **Output**: Analogico lineare

### Microcontrollore
- **Modello**: Adafruit Feather M4 CAN Express
- **Flash**: 2MB QSPI integrata per salvataggio dati
- **ADC**: 12-bit (risoluzione 0-4095)
- **Comunicazione**: USB seriale @ 115200 baud

---

## 💻 Requisiti Software

### GUI Python (PC)
- **Python**: 3.8 o superiore
- **Sistema Operativo**: Windows, macOS, Linux
- **Librerie richieste**:
  - `PyQt6` >= 6.4.0 (interfaccia grafica)
  - `pyqtgraph` >= 0.13.0 (grafici in tempo reale)
  - `pyserial` >= 3.5 (comunicazione seriale)
  - `numpy` >= 1.24.0 (elaborazione dati)

### Firmware Feather M4 CAN
- **PlatformIO** (consigliato) o Arduino IDE
- **Librerie**:
  - `Adafruit SPIFlash` >= 5.1.1
  - `SdFat - Adafruit Fork` >= 2.3.54

---

## 🚀 Installazione 

### 0. Installer .exe
Scaricare ed installare tramite il file .exe disponibile nella sezione "Release"

### 1. Installazione GUI Python

```bash
# Clona o scarica il repository
cd PressioneFreniGUI-PoliMarche

# Installa le dipendenze Python
pip install -r requirements.txt
```

### 2. Programmazione Feather M4 CAN

#### Opzione A: Con PlatformIO (Consigliato)

```bash
# Naviga nella cartella del firmware
cd GUI_Pressione_Freni

# Compila e carica il firmware
pio run --target upload
```

#### Opzione B: Con Arduino IDE

1. Installa l'Arduino IDE
2. Aggiungi il supporto per Adafruit SAMD boards:
   - File → Preferenze → URL aggiuntive per gestione schede
   - Aggiungi: `https://adafruit.github.io/arduino-board-index/package_adafruit_index.json`
3. Installa "Adafruit SAMD Boards" dal Board Manager
4. Installa le librerie richieste dal Library Manager:
   - Adafruit SPIFlash
   - SdFat - Adafruit Fork
5. Apri `GUI_Pressione_Freni/src/main.cpp`
6. Seleziona scheda: **Adafruit Feather M4 CAN (SAMD51)**
7. Carica lo sketch

---

## 🔌 Collegamenti Hardware

### Schema Collegamenti

```
Sensore di Pressione              Feather M4 CAN
┌─────────────────┐              ┌──────────────────┐
│                 │              │                  │
│  VCC (3.3V)     ├──────────────┤  3V3             │
│  GND            ├──────────────┤  GND             │
│  SIGNAL         ├──────────────┤  A4 (Pin 18)     │
│                 │              │                  │
└─────────────────┘              └──────────────────┘
                                          │
                                          │ USB
                                          ▼
                                      Computer
```

### Dettagli Pin

| Sensore | Feather M4 | Descrizione |
|---------|------------|-------------|
| **VCC** | **3V3** | Alimentazione sensore (3.3V) |
| **GND** | **GND** | Massa comune |
| **SIGNAL** | **A4** | Segnale analogico (0.33V - 2.97V) |

### Note sui Collegamenti
- ⚠️ **NON alimentare il sensore a 5V** - la Feather usa logica 3.3V
- Usare cavi schermati per ridurre interferenze
- Controllare la polarità prima di alimentare
- Il sensore è ratiometrico: l'output scala proporzionalmente con l'alimentazione

---

## 📖 Utilizzo

### Avvio del Sistema

1. **Connetti la Feather M4 CAN** al computer via USB
2. **Avvia la GUI (se uso manuale)**:
   ```bash
   python main.py
   ```
   **altrimenti avviare tramite il programma installato**

### Procedura Operativa

#### 1️⃣ Connessione
1. Seleziona la porta COM della Feather dal menu a tendina
2. Clicca **"Connetti"**
3. Verifica che lo status bar mostri "Connesso a COMX"

#### 2️⃣ Acquisizione Stint
1. Clicca **"Inizia Stint"** per avviare la registrazione
2. Il grafico si aggiorna in tempo reale (10 Hz)
3. I valori Min/Max/Media vengono calcolati automaticamente
4. Clicca **"Termina Stint"** al termine della sessione

#### 3️⃣ Salvataggio Dati
1. Dopo aver terminato uno stint, clicca **"Salva su Flash"**
2. I dati vengono trasferiti e salvati nella memoria della Feather
3. Il file viene nominato automaticamente: `stint_YYYYMMDD_HHMMSS.json`
4. Attendi conferma "Stint salvato su memoria flash!"

#### 4️⃣ Caricamento Stint Salvati
1. Clicca **"Carica da Flash"**
2. Seleziona lo stint desiderato dalla lista
3. Clicca **OK** per caricare e visualizzare i dati
4. Il grafico viene congelato automaticamente per l'analisi

#### 5️⃣ Esportazione CSV
1. Con uno stint caricato o grafico bloccato, clicca **"Esporta CSV"**
2. Il file CSV viene salvato nella cartella corrente
3. Formato: `stint_export_YYYYMMDD_HHMMSS.csv`

---

## ⚙️ Funzionalità

### Pannello Controlli

| Pulsante | Funzione | Stato Richiesto |
|----------|----------|-----------------|
| **Connetti/Disconnetti** | Stabilisce/chiude connessione seriale | - |
| **Aggiorna** | Ricarica lista porte COM disponibili | Disconnesso |
| **Inizia Stint** | Avvia registrazione dati | Connesso |
| **Termina Stint** | Ferma registrazione | Stint attivo |
| **Salva su Flash** | Salva stint su memoria Feather | Stint terminato |
| **Carica da Flash** | Carica stint salvato | Connesso |
| **Esporta CSV** | Esporta dati su file locale | Grafico bloccato |
| **Blocca/Sblocca Grafico** | Ferma/riprendi acquisizione | Connesso |
| **Gestisci Memoria** | Visualizza info, elimina file, formatta | Connesso |

### Visualizzazione Dati

#### Grafico Tempo Reale
- **Asse X**: Tempo in secondi dall'inizio acquisizione
- **Asse Y**: Pressione in bar (0-170 bar)
- **Aggiornamento**: 10 Hz (100ms)
- **Buffer**: Ultimi 1000 campioni (100 secondi)

#### Valori Istantanei
- **Pressione corrente**: Valore in tempo reale (font grande, grassetto)
- **Minimo**: Pressione minima rilevata
- **Massimo**: Pressione massima rilevata
- **Media**: Pressione media calcolata

### Gestione Memoria Flash

#### Informazioni Memoria
- Spazio totale disponibile (2 MB QSPI)
- Spazio utilizzato dagli stint
- Spazio libero rimanente
- Numero di file salvati

#### Operazioni
- **Elimina File Selezionati**: Rimuove stint specifici (selezione multipla)
- **Formatta**: Elimina TUTTI gli stint salvati (richiede conferma)

### Protezione Dati
- ✅ Disconnessione improvvisa gestita senza crash
- ✅ Reset automatico interfaccia in caso di errore
- ✅ Conferme prima di operazioni distruttive
- ✅ Verifica integrità file salvati
- ✅ Timeout su operazioni seriali

---

## 📊 Formato Dati

### Comunicazione Seriale (Feather → PC)

**Dati Real-Time**:
```
timestamp,pressione
12345,45.67
12445,46.12
12545,44.89
```

**Comandi/Risposte**:
```
// Lista file
FILES:
- stint_20251127_143022.json (5432 bytes)
- stint_20251127_150015.json (8901 bytes)
END_FILES

// Caricamento dati
DATA_START
{"date":"2025-11-27T14:30:22","duration":89.5,"samples":895,"data":[...]}
DATA_END

// Conferme
OK:File saved: /stints/stint_20251127_143022.json (5432 bytes)
ERROR:Flash not available
```

### File JSON (Memoria Flash)

```json
{
  "date": "2025-11-27T14:30:22.123456",
  "duration": 89.5,
  "samples": 895,
  "data": [
    {
      "timestamp": "14:30:22.123",
      "time": 0.0,
      "pressure": 0.45
    },
    {
      "timestamp": "14:30:22.223",
      "time": 0.1,
      "pressure": 12.34
    }
    // ... altri campioni
  ]
}
```

### File CSV Esportato

```csv
Tempo (s),Pressione (bar)
0.00,0.45
0.10,12.34
0.20,23.56
0.30,34.78
...
```

---

## 🔍 Calibrazione Sensore

Il sensore è configurato con i seguenti parametri:

```cpp
// Configurazione nel firmware
#define MAX_PRESSURE 170.0f    // Pressione massima (bar)
#define Vref 3.3f              // Tensione riferimento ADC
#define res 4095               // Risoluzione ADC (12-bit)

// Formula di conversione
float valoreADC = lettura_ADC * (Vref / res);
float pressione = (valoreADC - 0.33) * 170.0 / (2.97 - 0.33);
```

### Punti di Calibrazione
| Pressione (bar) | Tensione @ 3.3V | ADC (12-bit) |
|-----------------|-----------------|--------------|
| 0 | 0.33 V | ~410 |
| 85 (metà scala) | 1.65 V | ~2048 |
| 170 (fondo scala) | 2.97 V | ~3686 |

### Filtro Digitale
Il firmware implementa un **filtro a media mobile** (10 campioni) per ridurre il rumore dell'ADC.

---

## 🛠️ Troubleshooting

### Problemi Comuni

#### ❌ "Porta seriale disconnessa" durante l'uso
**Cause**:
- Cavo USB allentato
- Problemi di alimentazione
- Interferenze USB

**Soluzioni**:
- Controlla che il cavo sia ben inserito
- Usa una porta USB diretta (evita hub non alimentati)
- Il programma si resetterà automaticamente

#### ❌ "Flash not available"
**Cause**:
- Memoria flash non inizializzata
- Filesystem corrotto

**Soluzioni**:
1. Ricarica il firmware sulla Feather
2. Usa il comando "FORMAT" per riformattare
3. Verifica che le librerie SPIFlash siano installate correttamente

#### ❌ Valori di pressione errati
**Cause**:
- Collegamenti sbagliati
- Sensore guasto
- Calibrazione errata

**Soluzioni**:
1. Verifica i collegamenti (vedi schema sopra)
2. Controlla la tensione sul pin A4 con multimetro:
   - Riposo: ~0.33V
   - Pressione applicata: aumenta fino a 2.97V
3. Verifica che il sensore sia alimentato a 3.3V (NON 5V!)

#### ❌ GUI si blocca o crasha
**Soluzioni**:
- Aggiorna le librerie Python: `pip install --upgrade -r requirements.txt`
- Verifica compatibilità sistema operativo
- Controlla log errori nella console

#### ❌ Stint non si salva su flash
**Verifiche**:
1. Controlla spazio disponibile ("Gestisci Memoria")
2. Verifica che il file non sia troppo grande
3. Prova a formattare la memoria
4. Riavvia la Feather

---

## 📝 Protocollo Comandi Seriali

### Comandi PC → Feather

| Comando | Descrizione | Risposta |
|---------|-------------|----------|
| `SAVE:filename:json_data` | Salva stint su flash | `OK:...` o `ERROR:...` |
| `LIST` | Lista file salvati | `FILES:` ... `END_FILES` |
| `LOAD:filename` | Carica stint | `DATA_START` ... `DATA_END` |
| `DELETE:filename` | Elimina file | `OK:...` o `ERROR:...` |
| `INFO` | Info memoria | `INFO_START` ... `INFO_END` |
| `FORMAT` | Formatta memoria | `OK:...` |
| `DEBUG` | Info debug sistema | `DEBUG_INFO:` ... `END_DEBUG` |

---

## 📂 Struttura Progetto

```
PressioneFreniGUI-PoliMarche/
│
├── main.py                    # GUI Python principale
├── requirements.txt           # Dipendenze Python
├── README.md                  # Questa documentazione
├── LICENSE                    # Licenza GNU GPL v3
│
└── GUI_Pressione_Freni/      # Firmware Feather M4 CAN
    ├── platformio.ini         # Configurazione PlatformIO
    ├── src/
    │   └── main.cpp           # Codice firmware principale
    ├── include/
    ├── lib/
    └── test/
```

---

## 👨‍💻 Autore

**Alessandro Zingaretti**  
Polimarche Racing Team - UNIVPM  
Università Politecnica delle Marche

---

## 📜 Licenza

Questo progetto è rilasciato sotto licenza **GNU General Public License v3.0 (GPL-3.0)**.

Per il testo completo della licenza, consulta il file [LICENSE](LICENSE) o visita:  
https://www.gnu.org/licenses/gpl-3.0.html

**Copyright © 2025 Alessandro Zingaretti - Polimarche Racing Team**

---

## 🔄 Versione

**v1.0** - Novembre 2025
- Acquisizione dati real-time 10 Hz
- Salvataggio stint su flash QSPI
- Gestione completa memoria
- Esportazione CSV
- Protezione disconnessioni

---

## 📞 Supporto

Per problemi, domande o suggerimenti, puoi contattarmi tramite zingaale@gmail.com.

---

**🏁 Buona acquisizione dati! 🏁**
