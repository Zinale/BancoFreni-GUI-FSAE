/*
 * Feather M4 CAN - Lettura Sensore Pressione Freni
 * Legge il sensore ogni 100ms e invia dati via seriale
 * Gestisce salvataggio e caricamento stint nella memoria flash interna
 * 
 * Alessandro Zingaretti - Polimarche Racing Team - UNIVPM
 */

#include <Arduino.h>
#include <Adafruit_SPIFlash.h>
#include <SdFat.h>

// Configurazione sensore (calibrazione originale)
#define MAX_PRESSURE 124.67f
#define Vref 3.3f
#define res 4095
#define SENSOR_PIN A4

// Configurazione Flash interna
Adafruit_FlashTransport_QSPI flashTransport;
Adafruit_SPIFlash flash(&flashTransport);
FatFileSystem fatfs;

// Timing
const unsigned long READ_INTERVAL = 100;  // 100ms = 0.1s
unsigned long lastReadTime = 0;

// Buffer per comunicazione seriale
String serialBuffer = "";
bool flashAvailable = false;

int incremento = 1;
float bar = 0;

// Filtro media mobile per ridurre rumore ADC
#define FILTER_SIZE 10
float adcReadings[FILTER_SIZE];
int readIndex = 0;
float adcTotal = 0;
bool filterInitialized = false;

void handleSerialCommands();
void processCommand(String command);
void saveStintToSD(String filename, String data);
void listStintsOnSD();
void loadStintFromSD(String filename);
void deleteStintFromSD(String filename);
void getFlashInfo();
void formatStintsFolder();

void setup() {
  Serial.begin(115200); 
  
  while (!Serial) {
    delay(10);
  }
  
  Serial.println("Feather M4 CAN - Sensore Pressione Freni");
  Serial.println("Polimarche Racing Team - UNIVPM");
  Serial.println("Inizializzazione...");
  
  pinMode(SENSOR_PIN, INPUT);
  
  // Inizializza memoria Flash interna
  if (flash.begin()) {
    Serial.println("Flash inizializzata");
    
    // Monta il filesystem
    if (fatfs.begin(&flash)) {
      flashAvailable = true;
      Serial.println("Filesystem montato");
      
      // Crea cartella per gli stint se non esiste
      if (!fatfs.exists("/stints")) {
        fatfs.mkdir("/stints");
      }
    } else {
      Serial.println("ATTENZIONE: Impossibile montare filesystem");
    }
  } else {
    Serial.println("ATTENZIONE: Flash non disponibile");
  }
  
  Serial.println("Sistema pronto!");
  Serial.println("Formato dati: timestamp,pressione");
  Serial.println("---");
  analogReadResolution(12); // Imposta risoluzione ADC a 12 bit (0-4095)
  
  // Inizializza array filtro
  for (int i = 0; i < FILTER_SIZE; i++) {
    adcReadings[i] = 0;
  }
}

void loop() {
  unsigned long currentTime = millis();
  
  // Lettura sensore ogni 100ms
  if (currentTime - lastReadTime >= READ_INTERVAL) {
    lastReadTime = currentTime;
    
    // Lettura ADC con filtro media mobile
    float rawADC = analogRead(SENSOR_PIN);
    
    // Aggiorna media mobile
    adcTotal = adcTotal - adcReadings[readIndex];
    adcReadings[readIndex] = rawADC;
    adcTotal = adcTotal + adcReadings[readIndex];
    readIndex = (readIndex + 1) % FILTER_SIZE;
    
    if (!filterInitialized && readIndex == 0) {
      filterInitialized = true;
    }
    
    // Usa valore filtrato
    float filteredADC = adcTotal / FILTER_SIZE;
    float valoreADC = filteredADC * (Vref / res);
    
    // Calcolo pressione in bar
    // Formula lineare: 0.33V -> 0 bar, 2.97V -> 170 bar
    // Sensore ratiometrico: 0.5V@5V -> 0 bar, 4.5V@5V -> 170 bar
    // Con alimentazione 3.3V: 0.33V -> 0 bar, 2.97V -> 170 bar
    
    bar = (valoreADC - 0.33) * (170.0f) / (2.97f - 0.33f);
    
    // Limita i valori
    if (bar < 0) bar = 0;
    if (bar > 170.0f) bar = 170.0f;
    
    
    /*
    if (bar>255){
      incremento=-1;
    }
    if(bar< 1){
      incremento=1;
    }
    bar+=incremento;
    */

    // Invia dati nel formato: timestamp,pressione
    Serial.print(currentTime);
    Serial.print(",");
    Serial.println(bar, 2);
  }
  
  // Gestione comandi dalla GUI
  handleSerialCommands();
}

void handleSerialCommands() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n') {
      processCommand(serialBuffer);
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}

void processCommand(String command) {
  command.trim();
  
  if (command.startsWith("SAVE:")) {
    // Formato: SAVE:filename:json_data
    int firstColon = command.indexOf(':');
    int secondColon = command.indexOf(':', firstColon + 1);
    
    if (secondColon > 0) {
      String filename = command.substring(firstColon + 1, secondColon);
      String data = command.substring(secondColon + 1);
      
      saveStintToSD(filename, data);
    }
  } 
  else if (command == "LIST") {
    listStintsOnSD();
  } 
  else if (command.startsWith("LOAD:")) {
    String filename = command.substring(5);
    loadStintFromSD(filename);
  }
  else if (command.startsWith("DELETE:")) {
    String filename = command.substring(7);
    deleteStintFromSD(filename);
  }
  else if (command == "INFO") {
    getFlashInfo();
  }
  else if (command == "FORMAT") {
    formatStintsFolder();
  }
  else if (command == "DEBUG") {
    // Comando di debug per verificare filesystem
    Serial.println("DEBUG_INFO:");
    Serial.print("Flash available: ");
    Serial.println(flashAvailable ? "YES" : "NO");
    
    if (flashAvailable) {
      Serial.print("Flash size: ");
      Serial.print(flash.size() / 1024);
      Serial.println(" KB");
      
      Serial.print("/stints exists: ");
      Serial.println(fatfs.exists("/stints") ? "YES" : "NO");
    }
    Serial.println("END_DEBUG");
  }
}

void saveStintToSD(String filename, String data) {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  String filepath = "/stints/" + filename;
  
  // Apri file in scrittura
  File dataFile = fatfs.open(filepath.c_str(), FILE_WRITE);
  
  if (dataFile) {
    size_t bytesWritten = dataFile.println(data);
    dataFile.flush();  // Forza scrittura su flash
    dataFile.close();
    
    // Verifica che il file esista effettivamente
    if (fatfs.exists(filepath.c_str())) {
      Serial.print("OK:File saved: ");
      Serial.print(filepath);
      Serial.print(" (");
      Serial.print(bytesWritten);
      Serial.println(" bytes)");
    } else {
      Serial.println("ERROR:File saved but not found after close");
    }
  } else {
    Serial.println("ERROR:Cannot open file");
  }
}

void listStintsOnSD() {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  // Verifica che la cartella stints esista
  if (!fatfs.exists("/stints")) {
    Serial.println("ERROR:Stints folder does not exist");
    return;
  }
  
  File root = fatfs.open("/stints");
  
  if (!root) {
    Serial.println("ERROR:Cannot open stints folder");
    return;
  }
  
  if (!root.isDirectory()) {
    Serial.println("ERROR:/stints is not a directory");
    root.close();
    return;
  }
  
  Serial.println("FILES:");
  
  int fileCount = 0;
  root.rewindDirectory();
  
  while (true) {
    File entry = root.openNextFile();
    if (!entry) {
      break;
    }
    
    if (!entry.isDirectory()) {
      char filename[64];
      entry.getName(filename, sizeof(filename));
      
      // Estrai solo il nome del file senza il path
      const char* fileName = filename;
      const char* lastSlash = strrchr(filename, '/');
      if (lastSlash != NULL) {
        fileName = lastSlash + 1;
      }
      
      Serial.print("- ");
      Serial.print(fileName);
      Serial.print(" (");
      Serial.print(entry.size());
      Serial.println(" bytes)");
      fileCount++;
    }
    
    entry.close();
  }
  
  root.close();
  Serial.println("END_FILES");
  
  if (fileCount == 0) {
    Serial.println("INFO:No files found");
  }
}

void loadStintFromSD(String filename) {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  // Debug: mostra cosa si sta cercando di caricare
  Serial.print("DEBUG:Trying to load: ");
  Serial.println(filename);
  
  String filepath = "/stints/" + filename;
  
  Serial.print("DEBUG:Full path: ");
  Serial.println(filepath);
  
  // Verifica se il file esiste
  if (!fatfs.exists(filepath.c_str())) {
    Serial.print("ERROR:File does not exist: ");
    Serial.println(filepath);
    return;
  }
  
  File dataFile = fatfs.open(filepath.c_str(), FILE_READ);
  
  if (dataFile) {
    Serial.println("DATA_START");
    
    while (dataFile.available()) {
      Serial.write(dataFile.read());
    }
    
    dataFile.close();
    Serial.println();
    Serial.println("DATA_END");
  } else {
    Serial.println("ERROR:Cannot open file");
  }
}

void deleteStintFromSD(String filename) {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  String filepath = "/stints/" + filename;
  
  if (!fatfs.exists(filepath.c_str())) {
    Serial.print("ERROR:File does not exist: ");
    Serial.println(filepath);
    return;
  }
  
  if (fatfs.remove(filepath.c_str())) {
    Serial.print("OK:File deleted: ");
    Serial.println(filename);
  } else {
    Serial.println("ERROR:Cannot delete file");
  }
}

void getFlashInfo() {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  Serial.println("INFO_START");
  
  // Dimensione totale flash
  uint32_t totalSize = flash.size();
  Serial.print("Total: ");
  Serial.println(totalSize);
  
  // Calcola spazio usato nella cartella stints
  uint32_t usedSpace = 0;
  int fileCount = 0;
  
  if (fatfs.exists("/stints")) {
    File root = fatfs.open("/stints");
    if (root && root.isDirectory()) {
      root.rewindDirectory();
      
      while (true) {
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory()) {
          usedSpace += entry.size();
          fileCount++;
        }
        entry.close();
      }
      root.close();
    }
  }
  
  Serial.print("Used: ");
  Serial.println(usedSpace);
  Serial.print("Files: ");
  Serial.println(fileCount);
  
  Serial.println("INFO_END");
}

void formatStintsFolder() {
  if (!flashAvailable) {
    Serial.println("ERROR:Flash not available");
    return;
  }
  
  int deletedCount = 0;
  
  if (fatfs.exists("/stints")) {
    File root = fatfs.open("/stints");
    if (root && root.isDirectory()) {
      root.rewindDirectory();
      
      // Raccoglie i nomi dei file da eliminare
      String filesToDelete[50];  // Max 50 file
      int fileCount = 0;
      
      while (true) {
        File entry = root.openNextFile();
        if (!entry) break;
        
        if (!entry.isDirectory() && fileCount < 50) {
          char filename[64];
          entry.getName(filename, sizeof(filename));
          filesToDelete[fileCount++] = String(filename);
        }
        entry.close();
      }
      root.close();
      
      // Elimina i file
      for (int i = 0; i < fileCount; i++) {
        if (fatfs.remove(filesToDelete[i].c_str())) {
          deletedCount++;
        }
      }
    }
  }
  
  Serial.print("OK:Formatted - ");
  Serial.print(deletedCount);
  Serial.println(" files deleted");
}