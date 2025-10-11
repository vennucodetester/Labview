"""
component_schemas.py (New File)

This file is the "DNA" of the diagram editor. It provides a definitive schema
for every component that can exist in the system. Each schema defines:
- `properties`: User-editable parameters (e.g., cooling_type of a condenser).
- `ports`: Connection points for pipes, with types and fluid states.
- `zones`: Special non-connection areas for sensor drops (e.g., shelves).
- `dynamic_ports`: Rules for creating ports programmatically (e.g., a distributor).

This centralized, modular approach allows for easy extension. To add a new
component type to the application, you only need to add its definition here.
"""

SCHEMAS = {
    "CaseShell": {
        "properties": {
            "case_length": {"type": "integer", "default": 12, "units": "ft"}
        },
        "ports": [
            {"name": "return_air_in", "type": "in", "fluid_state": "air", "position": [0, 0.5]},
            {"name": "discharge_air_out", "type": "out", "fluid_state": "air", "position": [1, 0.5]}
        ],
        "zones": [
            {"name": "shelf_1", "rect": [0.1, 0.2, 0.8, 0.1]},  # x, y, w, h in %
            {"name": "shelf_2", "rect": [0.1, 0.4, 0.8, 0.1]}
        ]
    },
    "Compressor": {
        "properties": {"type": {"type": "string", "default": "Scroll"}},
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "gas", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "gas", "position": [1, 0.5]}
        ]
    },
    "Condenser": {
        "properties": {"cooling_type": {"type": "enum", "options": ["Air-Cooled", "Water-Cooled"], "default": "Air-Cooled"}},
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "gas", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "liquid", "position": [1, 0.5]}
        ]
    },
    "Evaporator": {
        "properties": {"circuits": {"type": "integer", "default": 1}},
        "ports": [
            {"name": "inlet_main", "type": "in", "fluid_state": "two-phase", "position": [0, 0.5]}
        ],
        "dynamic_ports": {
            "prefix": "outlet_circuit_",
            "count_property": "circuits",
            "port_details": {"type": "out", "fluid_state": "gas"}
        },
        "zones": [
            {"name": "coil_surface", "rect": [0.2, 0.2, 0.6, 0.6]}
        ]
    },
    "Distributor": {
        "properties": {"circuit_count": {"type": "integer", "default": 1}},
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "two-phase", "position": [0, 0.5]}
        ],
        "dynamic_ports": {
            "prefix": "outlet_",
            "count_property": "circuit_count",
            "port_details": {"type": "out", "fluid_state": "two-phase"}
        }
    },
    "TXV": {
        "properties": {},
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "two-phase", "position": [1, 0.5]},
            {"name": "bulb_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 1]}
        ]
    },
    "SolenoidValve": {
        "properties": {"purpose": {"type": "enum", "options": ["Liquid Line", "Hot Gas Defrost", "Cool Gas Defrost"], "default": "Liquid Line"}},
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "any", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "any", "position": [1, 0.5]}
        ]
    },
    "Fan": {
        "properties": {
            "type": {"type": "enum", "options": ["Evaporator", "Condenser"], "default": "Evaporator"},
            "diameter": {"type": "integer", "default": 10, "units": "in"}
        },
        "ports": []
    },
    
    # === Additional Refrigeration Components ===
    
    "Receiver": {
        "properties": {
            "capacity": {"type": "integer", "default": 5, "units": "gallons"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0.5, 0]},
            {"name": "outlet", "type": "out", "fluid_state": "liquid", "position": [0.5, 1]}
        ],
        "zones": [
            {"name": "liquid_level", "rect": [0.2, 0.4, 0.6, 0.3]}
        ]
    },
    
    "Accumulator": {
        "properties": {
            "capacity": {"type": "integer", "default": 3, "units": "gallons"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "gas", "position": [0.5, 1]},
            {"name": "outlet", "type": "out", "fluid_state": "gas", "position": [0.5, 0]}
        ],
        "zones": [
            {"name": "oil_return", "rect": [0.2, 0.7, 0.6, 0.2]}
        ]
    },
    
    "FilterDrier": {
        "properties": {
            "size": {"type": "enum", "options": ["1/2", "5/8", "3/4", "7/8"], "default": "5/8", "units": "inch"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "liquid", "position": [1, 0.5]}
        ]
    },
    
    "SightGlass": {
        "properties": {
            "has_moisture_indicator": {"type": "enum", "options": ["Yes", "No"], "default": "Yes"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "liquid", "position": [1, 0.5]}
        ],
        "zones": [
            {"name": "viewing_window", "rect": [0.3, 0.3, 0.4, 0.4]}
        ]
    },
    
    "CheckValve": {
        "properties": {
            "direction": {"type": "enum", "options": ["Horizontal", "Vertical"], "default": "Horizontal"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "any", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "any", "position": [1, 0.5]}
        ]
    },
    
    "PressureRegulator": {
        "properties": {
            "type": {"type": "enum", "options": ["EPR", "CPR", "CRANKCASE"], "default": "EPR"},
            "setpoint": {"type": "integer", "default": 10, "units": "psig"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "gas", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "gas", "position": [1, 0.5]},
            {"name": "sense_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 1]}
        ]
    },
    
    "HeatExchanger": {
        "properties": {
            "type": {"type": "enum", "options": ["Suction Line", "Liquid Line"], "default": "Suction Line"}
        },
        "ports": [
            {"name": "liquid_in", "type": "in", "fluid_state": "liquid", "position": [0, 0.3]},
            {"name": "liquid_out", "type": "out", "fluid_state": "liquid", "position": [1, 0.3]},
            {"name": "suction_in", "type": "in", "fluid_state": "gas", "position": [0, 0.7]},
            {"name": "suction_out", "type": "out", "fluid_state": "gas", "position": [1, 0.7]}
        ]
    },
    
    "OilSeparator": {
        "properties": {
            "capacity": {"type": "integer", "default": 2, "units": "gallons"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "gas", "position": [0, 0.3]},
            {"name": "outlet", "type": "out", "fluid_state": "gas", "position": [1, 0.3]},
            {"name": "oil_return", "type": "out", "fluid_state": "liquid", "position": [0.5, 1]}
        ]
    },
    
    "SubCooler": {
        "properties": {
            "type": {"type": "enum", "options": ["Mechanical", "Liquid Injection"], "default": "Mechanical"}
        },
        "ports": [
            {"name": "main_liquid_in", "type": "in", "fluid_state": "liquid", "position": [0, 0.3]},
            {"name": "main_liquid_out", "type": "out", "fluid_state": "liquid", "position": [1, 0.3]},
            {"name": "subcool_in", "type": "in", "fluid_state": "any", "position": [0, 0.7]},
            {"name": "subcool_out", "type": "out", "fluid_state": "any", "position": [1, 0.7]}
        ]
    },
    
    "Defrost": {
        "properties": {
            "type": {"type": "enum", "options": ["Hot Gas", "Electric", "Off-Cycle"], "default": "Hot Gas"}
        },
        "ports": [
            {"name": "hot_gas_in", "type": "in", "fluid_state": "gas", "position": [0, 0.5]},
            {"name": "drain_out", "type": "out", "fluid_state": "liquid", "position": [0.5, 1]}
        ]
    },
    
    "Strainer": {
        "properties": {
            "mesh_size": {"type": "integer", "default": 100, "units": "microns"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "liquid", "position": [1, 0.5]}
        ]
    },
    
    "PressureTransducer": {
        "properties": {
            "range": {"type": "string", "default": "0-500 psig"}
        },
        "ports": [
            {"name": "sense_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 0.5]}
        ]
    },
    
    "TemperatureSensor": {
        "properties": {
            "type": {"type": "enum", "options": ["RTD", "Thermocouple", "Thermistor"], "default": "RTD"}
        },
        "ports": [
            {"name": "sense_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 0.5]}
        ]
    },
    
    "ExpansionValve": {
        "properties": {
            "type": {"type": "enum", "options": ["TEV", "EEV", "AEV"], "default": "TEV"}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]},
            {"name": "outlet", "type": "out", "fluid_state": "two-phase", "position": [1, 0.5]},
            {"name": "bulb_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 1]},
            {"name": "equalizer_port", "type": "sensor", "fluid_state": "none", "position": [0.5, 0]}
        ]
    },
    
    "SuctionHeader": {
        "properties": {
            "circuit_count": {"type": "integer", "default": 2}
        },
        "ports": [
            {"name": "outlet", "type": "out", "fluid_state": "gas", "position": [1, 0.5]}
        ],
        "dynamic_ports": {
            "prefix": "inlet_",
            "count_property": "circuit_count",
            "port_details": {"type": "in", "fluid_state": "gas"}
        }
    },
    
    "LiquidManifold": {
        "properties": {
            "outlet_count": {"type": "integer", "default": 2}
        },
        "ports": [
            {"name": "inlet", "type": "in", "fluid_state": "liquid", "position": [0, 0.5]}
        ],
        "dynamic_ports": {
            "prefix": "outlet_",
            "count_property": "outlet_count",
            "port_details": {"type": "out", "fluid_state": "liquid"}
        }
    },
    
    "CondensingUnit": {
        "properties": {
            "hp": {"type": "integer", "default": 5, "units": "HP"}
        },
        "ports": [
            {"name": "suction_in", "type": "in", "fluid_state": "gas", "position": [0, 0.5]},
            {"name": "discharge_out", "type": "out", "fluid_state": "gas", "position": [1, 0.5]}
        ],
        "zones": [
            {"name": "compressor_area", "rect": [0.2, 0.6, 0.3, 0.3]},
            {"name": "condenser_area", "rect": [0.5, 0.2, 0.4, 0.4]}
        ]
    }
}

