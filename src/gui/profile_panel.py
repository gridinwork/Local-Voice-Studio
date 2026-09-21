"""Left-side panel: Voice Profile selection and management."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from src.gui.record_dialog import RecordDialog
from src.profiles.voice_profile import VoiceProfile

try:
    import sounddevice as sd
    import soundfile as sf
except Exception:
    sd = None
    sf = None

QUALITY_COLORS = {
    "GOOD": "#4caf50",
    "ACCEPTABLE": "#ffb300",
    "BAD": "#e53935",
    "NO_DATA": "#666666",
}

QUALITY_LABELS_RU = {
    "GOOD": "ХОРОШО",
    "ACCEPTABLE": "ПРИЕМЛЕМО",
    "BAD": "ПЛОХО",
    "NO_DATA": "НЕТ ДАННЫХ",
}

REASON_LABELS_RU = {
    "too short": "слишком коротко",
    "clipping": "клиппинг",
    "low volume": "низкая громкость",
    "too much silence": "слишком много тишины",
    "too much noise": "слишком много шума",
    "elevated noise": "заметен фоновый шум (в пределах нормы)",
}


class ProfilePanel(QWidget):
    profile_changed = Signal(object)
    reference_text_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profile: VoiceProfile | None = None

        box = QGroupBox("VOICE PROFILE")
        layout = QVBoxLayout(box)

        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self._on_select)
        layout.addWidget(self.combo)

        self.btn_create = QPushButton("Создать")
        self.btn_delete = QPushButton("Удалить")
        self.btn_rename = QPushButton("Переименовать")
        self.btn_load = QPushButton("Загрузить MP3/WAV/FLAC")
        self.btn_record = QPushButton("Записать голос")
        self.btn_rebuild = QPushButton("Пересоздать профиль")
        for b in (self.btn_create, self.btn_delete, self.btn_rename,
                  self.btn_load, self.btn_record, self.btn_rebuild):
            layout.addWidget(b)

        layout.addWidget(QLabel("Референсы:"))
        self.ref_list = QListWidget()
        layout.addWidget(self.ref_list)
        self.btn_play_ref = QPushButton("▶ Прослушать референс")
        self.btn_use_ref_text = QPushButton("Использовать текст референса для генерации")
        self.btn_remove_ref = QPushButton("Удалить выбранный референс")
        layout.addWidget(self.btn_play_ref)
        layout.addWidget(self.btn_use_ref_text)
        layout.addWidget(self.btn_remove_ref)

        self.quality_label = QLabel("Reference quality: —")
        self.quality_label.setStyleSheet("font-weight: bold; padding: 6px;")
        layout.addWidget(self.quality_label)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        self.btn_create.clicked.connect(self._create_profile)
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_rename.clicked.connect(self._rename_profile)
        self.btn_load.clicked.connect(self._load_reference)
        self.btn_record.clicked.connect(self._record_reference)
        self.btn_rebuild.clicked.connect(self._rebuild_profile)
        self.btn_remove_ref.clicked.connect(self._remove_reference)
        self.btn_play_ref.clicked.connect(self._play_selected_reference)
        self.btn_use_ref_text.clicked.connect(self._use_selected_reference_text)

        self.refresh_profile_list()

    def refresh_profile_list(self, select: str | None = None):
        self.combo.blockSignals(True)
        self.combo.clear()
        names = VoiceProfile.list_all()
        self.combo.addItems(names)
        target = select if (select and select in names) else (names[0] if names else "")
        self.combo.setCurrentText(target)
        self.combo.blockSignals(False)
        self._on_select(target)

    def _on_select(self, name: str):
        if not name:
            self.current_profile = None
            self.ref_list.clear()
            self.quality_label.setText("Reference quality: —")
            self.profile_changed.emit(None)
            return
        try:
            self.current_profile = VoiceProfile.load(name)
        except FileNotFoundError:
            self.current_profile = None
            return
        self._refresh_refs()
        self.profile_changed.emit(self.current_profile)

    def _refresh_refs(self):
        self.ref_list.clear()
        if not self.current_profile:
            return
        for ref in self.current_profile.references:
            reasons = ", ".join(REASON_LABELS_RU.get(r, r) for r in ref.quality_reasons)
            label = f"{ref.filename} [{ref.quality}] {ref.duration_sec:.1f}s"
            if reasons:
                label += f" — {reasons}"
            item = QListWidgetItem(label)
            item.setData(1000, ref.filename)
            item.setToolTip(ref.transcript or "(текст не распознан)")
            self.ref_list.addItem(item)

        quality = self.current_profile.overall_quality()
        color = QUALITY_COLORS.get(quality, "#666666")
        label_ru = QUALITY_LABELS_RU.get(quality, quality)
        self.quality_label.setText(f"Reference quality: {label_ru}")
        self.quality_label.setStyleSheet(f"font-weight: bold; padding: 6px; color: {color};")

    def _create_profile(self):
        name, ok = QInputDialog.getText(self, "Создать профиль", "Имя профиля:")
        if not ok or not name.strip():
            return
        try:
            VoiceProfile.create(name.strip())
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        self.refresh_profile_list(select=name.strip())

    def _delete_profile(self):
        if not self.current_profile:
            return
        reply = QMessageBox.question(
            self, "Удалить профиль", f"Удалить профиль '{self.current_profile.name}' безвозвратно?"
        )
        if reply != QMessageBox.Yes:
            return
        VoiceProfile.delete(self.current_profile.name)
        self.refresh_profile_list()

    def _rename_profile(self):
        if not self.current_profile:
            return
        new_name, ok = QInputDialog.getText(self, "Переименовать профиль", "Новое имя:", text=self.current_profile.name)
        if not ok or not new_name.strip():
            return
        try:
            self.current_profile.rename(new_name.strip())
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        self.refresh_profile_list(select=new_name.strip())

    def _load_reference(self):
        if not self.current_profile:
            QMessageBox.information(self, "Нет профиля", "Сначала создайте или выберите Voice Profile.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Загрузить референс", "", "Аудио (*.mp3 *.wav *.flac *.m4a)"
        )
        last_entry = None
        for p in paths:
            try:
                last_entry = self.current_profile.add_reference(Path(p))
            except Exception as e:
                QMessageBox.warning(self, "Ошибка обработки", f"{Path(p).name}: {e}")
        self._refresh_refs()
        self.profile_changed.emit(self.current_profile)
        if last_entry is not None:
            self._select_reference(last_entry.filename)
            if last_entry.transcript:
                self.reference_text_ready.emit(last_entry.transcript)

    def _record_reference(self):
        if not self.current_profile:
            QMessageBox.information(self, "Нет профиля", "Сначала создайте или выберите Voice Profile.")
            return
        dialog = RecordDialog(self)
        if dialog.exec():
            wav_path = dialog.saved_path
            if wav_path:
                entry = None
                try:
                    entry = self.current_profile.add_reference(Path(wav_path))
                except Exception as e:
                    QMessageBox.warning(self, "Ошибка обработки", str(e))
                self._refresh_refs()
                self.profile_changed.emit(self.current_profile)
                if entry is not None:
                    self._select_reference(entry.filename)
                    if entry.transcript:
                        self.reference_text_ready.emit(entry.transcript)

    def _select_reference(self, filename: str):
        for i in range(self.ref_list.count()):
            item = self.ref_list.item(i)
            if item.data(1000) == filename:
                self.ref_list.setCurrentItem(item)
                return

    def _play_selected_reference(self):
        item = self.ref_list.currentItem()
        if not item or not self.current_profile:
            QMessageBox.information(self, "Нет референса", "Выберите референс в списке.")
            return
        if sd is None or sf is None:
            QMessageBox.warning(self, "Ошибка", "sounddevice/soundfile не установлены.")
            return
        filename = item.data(1000)
        path = self.current_profile.processed_dir / f"{Path(filename).stem}_clean.wav"
        if not path.exists():
            path = self.current_profile.reference_dir / filename
        try:
            data, sr = sf.read(str(path))
            sd.play(data, sr)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка воспроизведения", str(e))

    def _use_selected_reference_text(self):
        item = self.ref_list.currentItem()
        if not item or not self.current_profile:
            QMessageBox.information(self, "Нет референса", "Выберите референс в списке.")
            return
        filename = item.data(1000)
        entry = next((r for r in self.current_profile.references if r.filename == filename), None)
        if not entry or not entry.transcript:
            QMessageBox.information(self, "Нет текста", "Для этого референса текст не распознан.")
            return
        self.reference_text_ready.emit(entry.transcript)

    def _rebuild_profile(self):
        if not self.current_profile:
            return
        self.current_profile.rebuild()
        self._refresh_refs()
        self.profile_changed.emit(self.current_profile)
        QMessageBox.information(self, "Готово", "Профиль пересобран, кэш голоса будет пересчитан при следующей генерации.")

    def _remove_reference(self):
        if not self.current_profile:
            return
        item = self.ref_list.currentItem()
        if not item:
            return
        filename = item.data(1000)
        self.current_profile.remove_reference(filename)
        self._refresh_refs()
        self.profile_changed.emit(self.current_profile)
