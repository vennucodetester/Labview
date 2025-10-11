# Quick Start Guide

## Get Started in 5 Minutes

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Try These Features

#### Load Sample Data
1. Click **"Load Config"** button
2. Select `sample.json`
3. The diagram model and sensors will load

#### Build a Simple HVAC System
1. Go to **"Diagram Modeler"** tab
2. Click **"Compressor"** in toolbar
3. Click on canvas to place it
4. Click **"Condenser"** and place it
5. Click **"Evaporator"** and place it
6. Select any component to see properties on the right

#### View Sensor Data
1. Click **"Load CSV"** to load your data file
2. Go to **"Graph"** tab
3. Check sensors in the left panel to plot them
4. Use **"Select Custom Range"** to zoom into specific time periods

#### Compare Data
1. Go to **"Comparison"** tab
2. Load additional CSV files to compare
3. View side-by-side statistics

### Keyboard Shortcuts
- **ESC**: Clear sensor selection
- **Delete**: Remove selected diagram components

### Common Tasks

#### Save Your Work
```
Click "Save Config" → Enter filename → Click Save
```

#### Export a Graph
```
Graph tab → Click "Export" → graph_export.png is saved
```

#### Group Sensors
```
Right-click sensor(s) → "Create Group" → Enter name
```

### Troubleshooting

**App won't start?**
- Check Python version: `python --version` (need 3.10+)
- Install dependencies: `pip install -r requirements.txt`

**No data showing?**
- Make sure CSV has "Timestamp" column
- Check CSV format: first column = Timestamp, rest = sensor values

**Component won't delete?**
- Select it first (click once)
- Press Delete key while in "Diagram Modeler" tab

### Next Steps
- Read [README.md](README.md) for full documentation
- Check `DEBUG.txt` if you encounter errors
- Explore component schemas in `component_schemas.py`

---
**Happy analyzing!** 🚀

