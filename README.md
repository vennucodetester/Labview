# HVAC System Analyzer (Intelligent Modeler)

An advanced diagnostic tool for analyzing HVAC (Heating, Ventilation, and Air Conditioning) systems with interactive diagram modeling, real-time data visualization, and intelligent system analysis capabilities.

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Application Architecture](#application-architecture)
- [File Structure](#file-structure)
- [Component Schemas](#component-schemas)
- [Known Issues](#known-issues)
- [Development](#development)

## 🎯 Overview

This application provides a comprehensive platform for HVAC system diagnostics and analysis. It combines:
- **Interactive Diagram Modeling**: Build visual representations of HVAC systems
- **Real-time Data Visualization**: Plot sensor data with interactive graphs
- **CSV Data Analysis**: Compare multiple datasets and track system performance
- **Intelligent System Analysis**: Automated topology detection and description

## ✨ Features

### 1. Interactive Diagram Modeler
- **Component Palette**: Add HVAC components (compressors, condensers, evaporators, valves, etc.)
- **Drag-and-Drop Interface**: Visually design system topology
- **Property Editor**: Configure component-specific parameters
- **Schema-based Design**: Extensible component definitions
- **Delete & Modify**: Easily remove or update components

### 2. Graph Visualization
- **Time-series Plotting**: Visualize sensor data over time using pyqtgraph
- **Multi-sensor Support**: Plot multiple sensors simultaneously with color coding
- **Statistical Analysis**: Real-time stats (avg, min, max, delta) for each sensor
- **Custom Range Selection**: Interactive time range selection
- **Export Functionality**: Save graphs as images

### 3. Comparison View
- **Multi-file Comparison**: Compare base CSV with up to 2 additional files
- **Sensor Mapping**: Intelligent sensor name reconciliation
- **Side-by-side Analysis**: View statistics and differences
- **Color-coded Differences**: Visual indicators for data variances

### 4. Sensor Panel
- **Hierarchical Organization**: Group sensors for better management
- **Search Functionality**: Quick sensor filtering
- **Context Menu Operations**: Right-click for grouping, renaming, moving
- **CSV/Config Management**: Load and save session configurations

## 📦 Requirements

### Software Requirements
- **Python**: 3.10 or higher (tested on 3.13.2)
- **Operating System**: Windows 10/11, macOS, or Linux

### Python Packages
```
PyQt6>=6.4.0
pandas>=2.0.0
numpy>=1.24.0
pyqtgraph>=0.13.0
python-dateutil>=2.8.2
```

## 🚀 Installation

### Option 1: Using pip
```bash
# Clone or download the repository
cd "LAB DATA ANALYZER/GEMINI 2.0/DIAGNOSTIC TOOL"

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### Option 2: Using virtual environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## 📖 Usage

### Starting the Application
```bash
python app.py
```

### Loading Data
1. **Load CSV**: Click "Load CSV" button in the sensor panel
2. **Load Configuration**: Click "Load Config" to load a saved session (.json)
3. **Save Configuration**: Click "Save Config" to save your current session

### Building a Diagram
1. Navigate to the **Diagram Modeler** tab
2. Click a component from the toolbar (e.g., "Compressor")
3. Click on the canvas to place the component
4. Select and drag components to reposition them
5. Select a component to view/edit properties in the right panel
6. Press **Delete** key to remove selected components

### Viewing Graphs
1. Navigate to the **Graph** tab
2. Select sensors from the sensor panel to plot
3. Use **Reset Zoom** to restore default view
4. Use **Select Custom Range** to interactively choose a time range
5. Click **Export** to save the current graph

### Comparing Data
1. Navigate to the **Comparison** tab
2. Load base CSV data
3. Click **Load Comparison 1** or **Load Comparison 2**
4. Map sensor names if they differ
5. View side-by-side statistics and differences

## 🏗️ Application Architecture

### Design Pattern
The application follows a **Model-View-Controller (MVC)** pattern with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│                  MainWindow                     │
│              (Central Orchestrator)             │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
    ┌─────▼─────┐         ┌────▼────┐
    │DataManager│◄────────┤  Views  │
    │  (Model)  │         │(Widgets)│
    └───────────┘         └─────────┘
          │                     │
          │              ┌──────┴──────┐
          │              │             │
          │         ┌────▼───┐    ┌───▼─────┐
          │         │ Graph  │    │Diagram  │
          │         │ Widget │    │ Widget  │
          │         └────────┘    └─────────┘
          │
          └─► diagram_model
              ├─ components
              ├─ pipes
              ├─ sensor_roles
              └─ properties
```

### Core Components

#### DataManager (`data_manager.py`)
- **Central Data Hub**: Manages all application state
- **Diagram Model**: Stores component topology and properties
- **Signal Emission**: Notifies views of data changes
- **Session Management**: Load/save configurations

#### Component Schemas (`component_schemas.py`)
- **Declarative Definitions**: Each HVAC component has a schema
- **Properties**: User-configurable parameters
- **Ports**: Connection points for pipes
- **Zones**: Special areas for sensor placement
- **Dynamic Ports**: Programmatically generated ports (e.g., for distributors)

#### Diagram Widget (`diagram_widget.py`)
- **Interactive Canvas**: QGraphicsScene-based editor
- **Component Rendering**: Builds scene from data model
- **Property Editor**: Dock widget for editing component properties
- **User Interactions**: Handles mouse/keyboard events

#### Diagram Components (`diagram_components.py`)
- **Visual Elements**: QGraphicsItem subclasses
- **BaseComponentItem**: Renders individual components
- **PortItem**: Connection points visualization
- **PipeItem**: Fluid flow connections (Phase 2)

#### Graph Widget (`graph_widget.py`)
- **High-performance Plotting**: Uses pyqtgraph for fast rendering
- **DateAxisItem**: Timestamp-aware x-axis
- **Statistics Table**: Real-time sensor statistics
- **Interactive Range Selection**: Custom time range picker

#### Sensor Panel (`sensor_panel.py`)
- **Hierarchical Tree View**: Organized sensor display
- **Group Management**: Create, rename, delete sensor groups
- **Context Menu**: Rich right-click functionality
- **Search/Filter**: Quick sensor lookup

## 📁 File Structure

```
DIAGNOSTIC TOOL/
│
├── app.py                      # Main application entry point
├── data_manager.py             # Central data management class
├── component_schemas.py        # Component definitions (DNA of the editor)
├── diagram_widget.py           # Interactive diagram editor
├── diagram_components.py       # Visual component classes
├── graph_widget.py             # Time-series plotting widget
├── comparison_widget.py        # CSV comparison tool
├── sensor_panel.py             # Sensor list and grouping UI
├── mapping_dialog.py           # Sensor name mapping dialog
├── range_dialog.py             # Custom range selection dialog
├── system_analyzer.py          # Intelligent system analysis
│
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── DEBUG.txt                   # Runtime debug output
│
└── sample.json                 # Example session file
```

## 🔧 Component Schemas

The application uses a schema-based approach for defining HVAC components. Each schema includes:

```python
"ComponentName": {
    "properties": {
        "property_name": {
            "type": "string|integer|enum",
            "default": <value>,
            "options": [...]  # for enum types
        }
    },
    "ports": [
        {
            "name": "port_name",
            "type": "in|out|sensor",
            "fluid_state": "gas|liquid|two-phase|air",
            "position": [x, y]  # percentage (0-1)
        }
    ],
    "zones": [...]  # Optional sensor drop zones
}
```

### Available Components
- **CaseShell**: Display case with air zones
- **Compressor**: Refrigerant compressor
- **Condenser**: Air-cooled or water-cooled condenser
- **Evaporator**: Multi-circuit evaporator
- **Distributor**: Refrigerant distributor with dynamic ports
- **TXV**: Thermostatic expansion valve
- **SolenoidValve**: Liquid line or defrost valve
- **Fan**: Evaporator or condenser fan

### Adding New Components
To add a new component type:
1. Add its schema to `SCHEMAS` dict in `component_schemas.py`
2. Define properties, ports, and zones
3. No code changes needed elsewhere!

## ⚠️ Known Issues

### 1. PyQtGraph Compatibility
- **Issue**: `AttributeError: autoRangeEnabled` warnings in older versions
- **Status**: Does not affect functionality
- **Solution**: Upgrade to pyqtgraph 0.13.7+ or ignore warnings

### 2. Pipe Connections (Phase 2)
- **Status**: Visual pipe rendering not yet implemented
- **Workaround**: Use diagram for topology only

### 3. Smart Sensor Drop (Phase 3)
- **Status**: Drag-and-drop sensor assignment planned for future release

## 🛠️ Development

### Code Style
- **PEP 8**: Follow Python style guidelines
- **Docstrings**: Document all classes and methods
- **Comments**: Explain complex logic

### Adding Features

#### 1. Adding a New Widget/Tab
```python
# In app.py, add to setup_tabs():
self.new_widget = NewWidget(self.data_manager)
self.tabs.addTab(self.new_widget, "New Tab")
```

#### 2. Extending DataManager
```python
# In data_manager.py:
def new_method(self):
    # Manipulate self.diagram_model or self.csv_data
    self.data_changed.emit()  # Notify views
```

#### 3. Adding Component Properties
```python
# In component_schemas.py:
"NewComponent": {
    "properties": {
        "capacity": {"type": "integer", "default": 100, "units": "BTU/hr"}
    },
    "ports": [...]
}
```

### Testing
- **Manual Testing**: Run `python app.py` and test each feature
- **Sample Data**: Use `sample.json` for testing
- **Debug Output**: Check `DEBUG.txt` for runtime errors

### Debugging
Enable debug output:
```bash
python app.py 2>&1 | Tee-Object -FilePath DEBUG.txt
```

### Version History
- **v1.0** (Current): Initial release with interactive diagram modeler
  - Component palette and placement
  - Property editor
  - Graph visualization
  - CSV comparison
  - Session management

## 📝 License

[Specify your license here]

## 👥 Contributors

[Add contributors here]

## 📧 Contact

For questions, issues, or contributions, please contact [your contact information].

---

**Note**: This is an active development project. Features and APIs may change in future releases.

