"""
test_request_dialog.py

Phase 1 UI of the Test Request system (see TEST_REQUEST_PLAN.md).

TestRequestDialog — create/edit a test request:
  header (project, ELP type, title, objective)
  case + topology (drives Phase 3 auto-diagram later)
  parts (editable combos backed by the growing catalogs)
  settings, targets table
  Save → library/projects/<project>/requests/<id>.json
  Export → printable HTML test request

NewPartDialog — asked once when an unknown part number is typed.
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QGroupBox,
    QMessageBox, QInputDialog, QHeaderView, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt

from test_request_library import (
    TestRequestLibrary, PART_TYPES, PART_FIELD_DEFS, request_to_html,
    DEFAULT_TARGETS, compressor_to_rated_inputs, IN3_TO_CM3,
)


class NewPartDialog(QDialog):
    """Asked once when a new SUPPLIER part number enters a catalog.
    Fields are schema-driven: each one exists because a calculation,
    the diagram, or the scorecard consumes it."""

    def __init__(self, part_type: str, model: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'New {part_type} — add to catalog (one time)')
        self._fields = {}
        lay = QVBoxLayout(self)
        intro = QLabel(
            f"Supplier part number '<b>{model}</b>' is new to the "
            f"{part_type} catalog.\nEnter its datasheet values once — "
            f"every future test request reuses them automatically.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QFormLayout()
        for key, label, kind in PART_FIELD_DEFS.get(part_type, []):
            if isinstance(kind, tuple) and kind[0] == 'choice':
                w = QComboBox()
                w.addItems(kind[1])
            else:
                w = QLineEdit()
                if kind == 'float':
                    w.setPlaceholderText('number')
                    w.setMaximumWidth(160)
            self._fields[key] = (w, kind)
            form.addRow(label + ':', w)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def specs(self) -> dict:
        out = {}
        for key, (w, kind) in self._fields.items():
            if isinstance(w, QComboBox):
                v = w.currentText().strip()
            else:
                v = w.text().strip()
            if not v:
                continue
            if kind == 'float':
                try:
                    out[key] = float(v)
                except ValueError:
                    continue
            else:
                out[key] = v
        return out


class TestRequestDialog(QDialog):
    """Create or edit one test request."""

    def __init__(self, library: TestRequestLibrary, request: dict = None,
                 parent=None, data_manager=None):
        super().__init__(parent)
        self.lib = library
        self.data_manager = data_manager   # enables 'Apply to session'
        self.request = request          # None until a project is chosen (new)
        self.setWindowTitle('Test Request')
        self.setMinimumSize(600, 400)
        self.resize(780, 600)
        self._build_ui()
        if request:
            self._load(request)
        else:
            # New request: pre-seed the standard target rows
            for t in DEFAULT_TARGETS:
                self._add_target_row(t)

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)
        root = QVBoxLayout(body)
        root.setSpacing(12)
        root.setContentsMargins(14, 12, 14, 12)

        # Header -----------------------------------------------------------
        head = QGroupBox('Request')
        hf = QFormLayout(head)
        self.cmb_project = QComboBox()
        self.cmb_project.setEditable(True)
        self.cmb_project.addItems([p['name'] for p in self.lib.projects()])
        self.cmb_elp = QComboBox()
        self.cmb_elp.setEditable(True)
        for c in self.lib.elp_codes():
            self.cmb_elp.addItem(f"{c['code']} — {c['name']}", c['code'])
        self.txt_title = QLineEdit()
        self.txt_objective = QTextEdit()
        self.txt_objective.setMaximumHeight(70)
        hf.addRow('Project:', self.cmb_project)
        hf.addRow('Test type (ELP):', self.cmb_elp)
        hf.addRow('Title:', self.txt_title)
        hf.addRow('Objective:', self.txt_objective)
        root.addWidget(head)

        # Case / topology ----------------------------------------------------
        case = QGroupBox('Case & topology  (drives the auto-diagram later)')
        cf = QFormLayout(case)
        self.cmb_case_model = QComboBox()
        self.cmb_case_model.setEditable(True)
        self.cmb_case_model.addItems(self.lib.known_case_models())
        self.cmb_family = QComboBox()
        self.cmb_family.addItems(['Reach-in (non-modular)', 'Modular',
                                  'Cassette', 'Open', 'Doored'])
        self.cmb_system = QComboBox()
        self.cmb_system.addItems(['shared', 'cassette'])
        self.cmb_system.setMaximumWidth(220)
        self.spn_modules = QSpinBox(); self.spn_modules.setRange(1, 6)
        self.spn_modules.setMaximumWidth(120)
        self.spn_circuits = QSpinBox(); self.spn_circuits.setRange(1, 24)
        self.spn_circuits.setValue(6)
        self.spn_circuits.setMaximumWidth(120)
        self.cmb_cooling = QComboBox()
        self.cmb_cooling.addItems(['Water', 'Air'])
        self.cmb_cooling.setMaximumWidth(220)
        self.chk_doored = QCheckBox('Doored case')
        cf.addRow('Case model:', self.cmb_case_model)
        cf.addRow('Family:', self.cmb_family)
        cf.addRow('System type:', self.cmb_system)
        cf.addRow('Evaporator modules:', self.spn_modules)
        cf.addRow('Circuits per coil:', self.spn_circuits)
        cf.addRow('Condenser cooling:', self.cmb_cooling)
        cf.addRow('', self.chk_doored)
        root.addWidget(case)

        # Parts --------------------------------------------------------------
        parts = QGroupBox('Parts  (pick from catalog or type a new number — '
                          'new numbers are saved automatically)')
        pf = QFormLayout(parts)
        self.part_combos: dict[str, QComboBox] = {}
        for ptype in PART_TYPES:
            cmb = QComboBox()
            cmb.setEditable(True)
            cmb.addItem('')
            cmb.addItems(self.lib.catalog_models(ptype))
            self.part_combos[ptype] = cmb
            pf.addRow(ptype.title() + ':', cmb)
        root.addWidget(parts)

        # Settings -----------------------------------------------------------
        st = QGroupBox('Settings')
        sf = QFormLayout(st)
        self.txt_refrigerant = QLineEdit('R290')
        self.txt_refrigerant.setMaximumWidth(160)
        self.spn_charge = QDoubleSpinBox(); self.spn_charge.setRange(0, 10000)
        self.spn_charge.setSpecialValueText('—'); self.spn_charge.setDecimals(1)
        self.spn_charge.setMaximumWidth(160)
        self.spn_gpm = QDoubleSpinBox(); self.spn_gpm.setRange(0, 1000)
        self.spn_gpm.setSpecialValueText('—'); self.spn_gpm.setDecimals(2)
        self.spn_gpm.setMaximumWidth(160)
        self.spn_cfm = QDoubleSpinBox(); self.spn_cfm.setRange(0, 100000)
        self.spn_cfm.setSpecialValueText('—'); self.spn_cfm.setDecimals(0)
        self.spn_cfm.setMaximumWidth(160)
        self.txt_defrost = QLineEdit()
        self.txt_setpoints = QLineEdit()
        sf.addRow('Refrigerant:', self.txt_refrigerant)
        sf.addRow('Charge (oz):', self.spn_charge)
        sf.addRow('Water GPM:', self.spn_gpm)
        sf.addRow('Fan CFM:', self.spn_cfm)
        sf.addRow('Defrost (type / schedule):', self.txt_defrost)
        sf.addRow('Setpoints:', self.txt_setpoints)
        root.addWidget(st)

        # Targets ------------------------------------------------------------
        tg = QGroupBox('Targets — pass/fail criteria '
                       '(min/max blank = no limit on that side)')
        tv = QVBoxLayout(tg)
        self.tbl_targets = QTableWidget(0, 4)
        self.tbl_targets.setHorizontalHeaderLabels(['Target', 'Min', 'Max', 'Unit'])
        self.tbl_targets.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tbl_targets.setMaximumHeight(180)
        tv.addWidget(self.tbl_targets)
        btn_row = QHBoxLayout()
        b_add = QPushButton('+ Add target')
        b_add.clicked.connect(lambda: self._add_target_row())
        b_del = QPushButton('− Remove selected')
        b_del.clicked.connect(self._remove_target_row)
        btn_row.addWidget(b_add); btn_row.addWidget(b_del); btn_row.addStretch()
        tv.addLayout(btn_row)
        root.addWidget(tg)

        # Buttons ------------------------------------------------------------
        bb = QDialogButtonBox()
        self.btn_save = bb.addButton('Save',
                                     QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_export = bb.addButton('Save + Export printable',
                                       QDialogButtonBox.ButtonRole.ActionRole)
        if self.data_manager is not None:
            self.btn_diagram = bb.addButton('Generate process diagram',
                                            QDialogButtonBox.ButtonRole.ActionRole)
            self.btn_diagram.setToolTip(
                'Build the process diagram from this request’s topology — '
                'based on your own reference layout, nothing re-typed')
            self.btn_diagram.clicked.connect(self._on_generate_diagram)
            self.btn_apply = bb.addButton('Save + Apply to session',
                                          QDialogButtonBox.ButtonRole.ActionRole)
            self.btn_apply.setToolTip(
                'Save, then push this request into the current session: '
                'rated inputs from the compressor, water GPM, refrigerant, '
                'and compressor specs on the diagram')
            self.btn_apply.clicked.connect(self._on_apply)
        bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        self.btn_export.clicked.connect(self._on_export)
        # Buttons live OUTSIDE the scroll area so they are always visible
        bb.setContentsMargins(14, 6, 14, 10)
        outer.addWidget(bb)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _add_target_row(self, t: dict = None):
        r = self.tbl_targets.rowCount()
        self.tbl_targets.insertRow(r)
        vals = [t.get('name', '') if t else '',
                '' if not t or t.get('min') is None else str(t['min']),
                '' if not t or t.get('max') is None else str(t['max']),
                t.get('unit', '') if t else '']
        for c, v in enumerate(vals):
            self.tbl_targets.setItem(r, c, QTableWidgetItem(v))

    def _remove_target_row(self):
        r = self.tbl_targets.currentRow()
        if r >= 0:
            self.tbl_targets.removeRow(r)

    def _targets_from_table(self) -> list:
        out = []
        for r in range(self.tbl_targets.rowCount()):
            def cell(c):
                it = self.tbl_targets.item(r, c)
                return it.text().strip() if it else ''
            name = cell(0)
            if not name:
                continue
            def num(c):
                v = cell(c)
                try:
                    return float(v) if v else None
                except ValueError:
                    return None
            out.append({'name': name, 'min': num(1), 'max': num(2),
                        'unit': cell(3)})
        return out

    def _load(self, rq: dict):
        proj = next((p for p in self.lib.projects()
                     if p['id'] == rq.get('project_id')), None)
        if proj:
            self.cmb_project.setCurrentText(proj['name'])
        self.cmb_elp.setCurrentText(rq.get('elp_code', ''))
        self.txt_title.setText(rq.get('title', ''))
        self.txt_objective.setPlainText(rq.get('objective', ''))
        self.cmb_case_model.setCurrentText(rq.get('case_model', ''))
        topo = rq.get('topology', {})
        self.cmb_family.setCurrentText(topo.get('case_family', ''))
        self.cmb_system.setCurrentText(topo.get('system_type', 'shared'))
        self.spn_modules.setValue(int(topo.get('modules', 1) or 1))
        self.spn_circuits.setValue(int(topo.get('circuits_per_coil', 6) or 6))
        self.cmb_cooling.setCurrentText(topo.get('condenser_cooling', 'Water'))
        self.chk_doored.setChecked(bool(topo.get('doored')))
        for ptype, cmb in self.part_combos.items():
            p = rq.get('parts', {}).get(ptype)
            cmb.setCurrentText(p.get('model', '') if p else '')
        s = rq.get('settings', {})
        self.txt_refrigerant.setText(s.get('refrigerant', 'R290'))
        if s.get('charge_oz'):
            self.spn_charge.setValue(float(s['charge_oz']))
        if s.get('water_gpm'):
            self.spn_gpm.setValue(float(s['water_gpm']))
        if s.get('fan_cfm'):
            self.spn_cfm.setValue(float(s['fan_cfm']))
        self.txt_defrost.setText(s.get('defrost', ''))
        self.txt_setpoints.setText(s.get('setpoints', ''))
        self.tbl_targets.setRowCount(0)
        for t in rq.get('targets', []):
            self._add_target_row(t)

    # ── save / export ────────────────────────────────────────────────────────
    def _collect(self) -> bool:
        proj_name = self.cmb_project.currentText().strip()
        if not proj_name:
            QMessageBox.warning(self, 'Missing', 'Enter a project name.')
            return False
        project = self.lib.add_project(proj_name)
        if self.request is None:
            self.request = self.lib.new_request(project['id'])
        self.request['project_id'] = project['id']

        elp_text = self.cmb_elp.currentText().strip()
        elp_code = elp_text.split(' — ')[0].strip() if elp_text else ''
        if elp_code and not any(c['code'].lower() == elp_code.lower()
                                for c in self.lib.elp_codes()):
            name, ok = QInputDialog.getText(
                self, 'New test type',
                f"'{elp_code}' is a new test type. Short name for it:")
            self.lib.add_elp_code(elp_code, name if ok and name else elp_code)
        self.request['elp_code'] = elp_code
        self.request['title'] = self.txt_title.text().strip()
        self.request['objective'] = self.txt_objective.toPlainText().strip()
        self.request['case_model'] = self.cmb_case_model.currentText().strip()
        self.request['topology'] = {
            'case_family': self.cmb_family.currentText(),
            'system_type': self.cmb_system.currentText(),
            'modules': self.spn_modules.value(),
            'circuits_per_coil': self.spn_circuits.value(),
            'condenser_cooling': self.cmb_cooling.currentText(),
            'doored': self.chk_doored.isChecked(),
        }
        for ptype, cmb in self.part_combos.items():
            model = cmb.currentText().strip()
            if model and not self.lib.find_part(ptype, model):
                dlg = NewPartDialog(ptype, model, self)
                specs = dlg.specs() if dlg.exec() else {}
                self.lib.add_part(ptype, model, specs)
            self.lib.attach_part(self.request, ptype, model)
        self.request['settings'] = {
            'refrigerant': self.txt_refrigerant.text().strip() or 'R290',
            'charge_oz': self.spn_charge.value() or None,
            'water_gpm': self.spn_gpm.value() or None,
            'fan_cfm': self.spn_cfm.value() or None,
            'defrost': self.txt_defrost.text().strip(),
            'setpoints': self.txt_setpoints.text().strip(),
        }
        self.request['targets'] = self._targets_from_table()
        # Targets double as the per-case criteria file (Phase 2 scorecard)
        if self.request['case_model']:
            self.lib.save_case_targets(self.request['case_model'],
                                       self.request['targets'])
        return True

    def _on_save(self):
        if not self._collect():
            return
        self.lib.save_request(self.request)
        self.accept()

    def _on_generate_diagram(self):
        """Save, then build the process diagram from the request topology and
        load it into the Diagram tab (replacing the current diagram)."""
        if not self._collect():
            return
        self.lib.save_request(self.request)
        dm = self.data_manager
        if (dm.diagram_model or {}).get('components'):
            ans = QMessageBox.question(
                self, 'Replace diagram?',
                'The current session already has a process diagram.\n'
                'Replace it with one generated from this test request?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        try:
            from diagram_from_request import build_bare_minimum_diagram
            model = build_bare_minimum_diagram(self.request)
        except Exception as e:
            QMessageBox.critical(self, 'Generation failed', str(e))
            return
        model.pop('_generated_from', None)
        dm.diagram_model.clear()
        dm.diagram_model.update(model)
        dm.diagram_model_changed.emit()
        topo = self.request.get('topology', {})
        QMessageBox.information(
            self, 'Diagram generated',
            f"Process diagram built from this request:\n"
            f"• {topo.get('modules')} module(s), "
            f"{topo.get('circuits_per_coil')} circuits per coil\n"
            f"• {topo.get('condenser_cooling')}-cooled condenser\n\n"
            f"Switch to the Diagram tab to see it. Sensors are unmapped — "
            f"map them when the first CSV arrives.")
        # Jump to the Diagram tab if we can reach the main window
        try:
            mw = self.parent()
            if mw is not None and hasattr(mw, 'tabs') and hasattr(mw, 'diagram_widget'):
                mw.tabs.setCurrentWidget(mw.diagram_widget)
        except Exception:
            pass
        self.accept()

    def _on_apply(self):
        """Save, then push this request's data into the live session —
        the wire that makes the catalog pay rent: no more re-typing
        rated inputs."""
        if not self._collect():
            return
        self.lib.save_request(self.request)
        dm = self.data_manager
        applied = []

        # 1. Compressor datasheet → rated inputs (ft³/Hz conversions inside)
        comp = self.request.get('parts', {}).get('compressor')
        gpm = self.request.get('settings', {}).get('water_gpm')
        if comp:
            rated = compressor_to_rated_inputs(comp.get('snapshot', {}), gpm)
            if rated:
                dm.rated_inputs.update(rated)
                applied.append(f"Rated inputs ({len(rated)} fields) from "
                               f"{comp.get('model')}")
        elif gpm:
            dm.rated_inputs['gpm_water'] = float(gpm)
            applied.append('Water GPM')

        # 2. Refrigerant
        refrig = self.request.get('settings', {}).get('refrigerant')
        if refrig:
            try:
                dm.refrigerant = refrig
                applied.append(f'Refrigerant = {refrig}')
            except Exception:
                pass

        # 3. Compressor specs onto diagram Compressor component(s) —
        #    activates the m_dot_disp cross-check
        if comp:
            snap = comp.get('snapshot', {})
            disp_in3 = snap.get('displacement_in3')
            rpm = snap.get('rated_speed_rpm')
            n = 0
            for c in (dm.diagram_model or {}).get('components', {}).values():
                if c.get('type') == 'Compressor':
                    props = c.setdefault('properties', {})
                    if disp_in3:
                        props['displacement_cm3'] = float(disp_in3) * IN3_TO_CM3
                    if rpm:
                        props['speed_rpm'] = float(rpm)
                    n += 1
            if n:
                applied.append(f'Compressor specs on {n} diagram component(s)')

        if applied:
            QMessageBox.information(
                self, 'Applied to session',
                'Pushed into the current session:\n• ' + '\n• '.join(applied)
                + '\n\nRe-run Calculations to use them.')
        else:
            QMessageBox.information(
                self, 'Nothing to apply',
                'Pick a compressor (with datasheet values) and/or set water '
                'GPM first.')
        self.accept()

    def _on_export(self):
        if not self._collect():
            return
        self.lib.save_request(self.request)
        proj = next((p for p in self.lib.projects()
                     if p['id'] == self.request['project_id']), {})
        html = request_to_html(self.request, proj.get('name', ''))
        out = os.path.join(self.lib.projects_dir, self.request['project_id'],
                           'requests', f"{self.request['id']}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
        try:
            os.startfile(out)  # opens in browser; print to PDF from there
        except Exception:
            pass
        QMessageBox.information(self, 'Exported',
                                f'Printable test request written to:\n{out}')
        self.accept()
