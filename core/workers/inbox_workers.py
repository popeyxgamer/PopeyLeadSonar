# -*- coding: utf-8 -*-
from PySide6.QtCore import QThread, Signal
from ..mailbox_reader import fetch_recent_messages, fetch_message_full, delete_message

class InboxFetchWorker(QThread):
    finished_ok = Signal(list)
    finished_error = Signal(str)
    def __init__(self, email, pwd, server):
        super().__init__()
        self.email = email; self.pwd = pwd; self.server = server
    def run(self):
        ok, msgs, err = fetch_recent_messages(self.email, self.pwd, self.server)
        if ok: self.finished_ok.emit(msgs)
        else: self.finished_error.emit(err)


class MessageFullWorker(QThread):
    finished_ok = Signal(object)
    finished_error = Signal(str)
    def __init__(self, email, pwd, server, uid):
        super().__init__()
        self.email = email; self.pwd = pwd; self.server = server; self.uid = uid
    def run(self):
        ok, msg, err = fetch_message_full(self.email, self.pwd, self.server, self.uid)
        if ok: self.finished_ok.emit(msg)
        else: self.finished_error.emit(err)


class MessageActionWorker(QThread):
    finished_ok = Signal()
    def __init__(self, action, email, pwd, server, uid, folder):
        super().__init__()
        self.action = action; self.email = email; self.pwd = pwd; self.server = server; self.uid = uid; self.folder = folder
    def run(self):
        if self.action == "delete":
            delete_message(self.email, self.pwd, self.server, self.uid, self.folder)
        self.finished_ok.emit()
