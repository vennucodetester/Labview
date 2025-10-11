"""
system_analyzer.py (New File)

This is the "intelligence layer" or "voice" of the application. It contains
functions that can inspect the diagram_model from the DataManager and produce
human-readable descriptions or perform high-level analysis.

It is completely decoupled from the UI. It takes a data model in and returns
information out, making it testable and purely logical.
"""

def describe_system(model):
    """
    Analyzes the diagram model and returns a human-readable string describing
    the system's topology.
    """
    if not model or not model.get('components'):
        return "System not yet defined."

    components = model.get('components', {})
    properties = model.get('properties', {})
    
    # --- Query the model ---
    evaps = [c for c in components.values() if c.get('type') == 'Evaporator']
    compressors = [c for c in components.values() if c.get('type') == 'Compressor']
    condensers = [c for c in components.values() if c.get('type') == 'Condenser']
    
    # --- Build the description string ---
    description = []
    
    # Evaporator count
    if len(evaps) == 1:
        description.append("This is a single coil case")
    else:
        description.append(f"This is a {len(evaps)} coil case")
        
    # Case properties
    if properties.get('case_length'):
        description.append(f" {properties['case_length']}ft long.")
    
    # Compressor topology (simplified for now)
    if len(compressors) == 1:
        description.append("It appears to be connected to a single compressor.")
    elif len(compressors) > 1:
        description.append(f"It uses {len(compressors)} compressors.")
        
    # Condenser type
    if condensers:
        cond_props = condensers[0].get('properties', {})
        cond_type = cond_props.get('cooling_type', 'unknown')
        description.append(f"It uses an {cond_type} condenser.")
        
    return "".join(description)
