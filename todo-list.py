#!env python3

#
# todo-list
# Copyright (C) 2017 https://github.com/ahagmann
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import sys
from PyQt4 import QtCore, QtGui, uic
import time
import re
import argparse
import json
import os
from functools import partial


ROOT = os.path.abspath(os.path.dirname(__file__))


def debug(s):
    #print("DEBUG: %s" % s)
    pass


class TagQSortFilterProxyModel(QtGui.QSortFilterProxyModel):
    def __init__(self, tag, parent=None):
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self.tag = tag
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if ('backlog' in item.tags) and (self.tag != 'backlog'):
            return False

        return self.tag in item.tags


class IssueQSortFilterProxyModel(QtGui.QSortFilterProxyModel):
    def __init__(self, parent=None):
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if 'backlog' in item.tags:
            return False

        return len(item.issues) > 0


class AllQSortFilterProxyModel(QtGui.QSortFilterProxyModel):
    def __init__(self, parent=None):
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if 'backlog' in item.tags:
            return False

        return True


class Tab(QtGui.QWidget):
    def __init__(self, model, filter, name, issue_link_prefix, parent=None):
        QtGui.QWidget.__init__(self, parent)
        uic.loadUi('tab.ui', self)

        self.name = name
        self.sourceModel = model
        self.issue_link_prefix = issue_link_prefix

        #self.view.viewport().setAutoFillBackground(False)

        if filter is None:
            self.model = AllQSortFilterProxyModel(self)
        elif filter == '_ISSUES':
            self.model = IssueQSortFilterProxyModel(self)
        else:
            self.model = TagQSortFilterProxyModel(filter, self)
        self.model.setSourceModel(model)
        self.view.setModel(self.model)

        self.view.customContextMenuRequested.connect(self.openIssue)

    def activeCount(self):
        c = 0
        for i in range(self.model.rowCount()):
            index = self.model.index(i, 0)
            source_index = self.model.mapToSource(index)
            item = self.sourceModel.item(source_index.row())
            if item.checkState() != 2 and item.empty is False:
                c += 1
        return c

    def openIssue(self, pos):
        if self.issue_link_prefix is not None:
            index = self.view.indexAt(pos)
            source_index = self.model.mapToSource(index)
            item = self.sourceModel.item(source_index.row())
            if len(item.issues) > 0:
                issue = item.issues[0]
                url = QtCore.QUrl(self.issue_link_prefix + issue)
                QtGui.QDesktopServices.openUrl(url)


class Item(QtGui.QStandardItem):
    def __init__(self, text='', done_timestamp=None):
        QtGui.QStandardItem.__init__(self, text)
        self.empty = True
        self.done_timestamp = done_timestamp
        self.tags = []
        self.issues = []
        if done_timestamp:
            self.setCheckState(2)

        self.updateState()

    def updateState(self):
        if self.text() != '':
            self.empty = False
            self.setCheckable(True)

        f = self.font()
        f.setStrikeOut(self.checkState())
        self.setFont(f)

        self.setEditable(not self.checkState())

        if self.checkState() == 2:
            if self.done_timestamp is None:
                self.done_timestamp = time.time()
                debug("checked %s" % self.text())
        else:
            self.done_timestamp = None

        self.tags = re.findall(r'#([A-Za-z][A-Za-z0-9]*)', self.text())
        self.issues = re.findall(r'#([0-9]+)', self.text())

    def __str__(self):
        return "%s (%s, %s, %s)" % (self.text(), str(self.done_timestamp), str(self.tags), str(self.issues))


class MainWindow(QtGui.QMainWindow):
    def __init__(self, args, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        uic.loadUi('mainwindow.ui', self)

        self.database_file = os.path.expanduser(args.database)
        self.issue_link_prefix = args.issue_link_prefix
        self.cleanup_time_h = args.cleanup_time

        self.model = QtGui.QStandardItemModel(self)

        all_tab = Tab(self.model, None, 'All', self.issue_link_prefix, self)
        self.tabs.addTab(all_tab, "All")

        issue_tab = Tab(self.model, '_ISSUES', "Issues", self.issue_link_prefix, self)
        self.tabs.addTab(issue_tab, "Issues")

        self.load()
        self.add_empty_item()

        self.model.itemChanged.connect(self.on_item_changed)
        self.actionClose.triggered.connect(self.closeTab)

        icon = QtGui.QIcon(os.path.join(ROOT, 'icon.png'))
        self.sys_tray_icon = QtGui.QSystemTrayIcon(self)
        self.sys_tray_icon.setIcon(icon)
        self.sys_tray_icon.setVisible(True)
        self.sys_tray_icon.activated.connect(self.tray_action)

        self.cleanup_timer = QtCore.QTimer(self)
        self.cleanup_timer.setInterval(10 * 60 * 1000)
        self.cleanup_timer.timeout.connect(self.cleanup)
        self.cleanup_timer.start()

    def add_empty_item(self):
        item = Item()
        self.model.appendRow(item)

    def on_item_changed(self, item):
        debug(item.row())
        empty = item.empty
        item.updateState()

        if empty is True and item.empty is False:
            self.add_empty_item()

        debug(item)
        self.updateMenu()
        self.updateItemCounters()

    def cleanup(self):
        duration = self.cleanup_time_h * 60 * 60
        for i in reversed(range(self.model.rowCount())):
            item = self.model.item(i)
            if item.done_timestamp:
                if item.done_timestamp < (time.time() - duration):
                    self.model.removeRow(item.row())
                    debug("remove %d" % i)

        self.store()

    def load(self):
        try:
            s = open(self.database_file).read()
            db = json.loads(s)
            if db['version'] == "1.0":
                for i in db['database']:
                    item = Item(i['text'], i['done_timestamp'])
                    self.model.appendRow(item)

                for i in db['tag_filter']:
                    self.addTagTab(i)
            else:
                raise "Unknown database version"

        except Exception as e:
            print("WARNING: Could not load database from '%s': %s" % (self.database_file, str(e)))

        self.updateMenu()
        self.updateItemCounters()

    def store(self):
        json_struct = {'version': "1.0", 'database': [], 'tag_filter': []}

        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.empty == False:
                json_struct['database'].append({'text': item.text(), 'done_timestamp': item.done_timestamp})

        for i in range(self.tabs.count()):
            if i > 1:
                json_struct['tag_filter'].append(self.tabs.widget(i).name)

        s = json.dumps(json_struct, sort_keys=True, indent=4, separators=(',', ': '))
        with open(self.database_file, 'w') as f:
            f.write(s)

    def updateMenu(self):
        tags = []
        for i in range(self.model.rowCount()):
            tags += self.model.item(i).tags
        tags = sorted(list(set(tags)))

        self.menuAdd.clear()
        for tag in tags:
            action = QtGui.QAction(tag, self)
            self.menuAdd.addAction(action)
            action.triggered[()].connect(partial(self.addTagTab, tag))

    def updateItemCounters(self):
        for i in range(self.tabs.count()):
            c = self.tabs.widget(i).activeCount()
            n = self.tabs.widget(i).name
            label = "%s (%d)" % (n, c)
            self.tabs.setTabText(i, label)

    def addTagTab(self, tag):
        tab = Tab(self.model, tag, tag, self.issue_link_prefix, self)
        self.tabs.addTab(tab, tag)

        self.updateItemCounters()

    def closeTab(self):
        i = self.tabs.currentIndex()
        if i > 1:
            self.tabs.removeTab(i)

    def closeEvent(self, event):
        QtGui.QMainWindow.closeEvent(self, event)
        self.store()

    def tray_action(self, reason):
        if reason == QtGui.QSystemTrayIcon.Trigger:
            self.hide()
            self.setGeometry(self.geometry())
            self.show()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)

    parser = argparse.ArgumentParser("todo-list utility")
    parser.add_argument('--database', default='~/.todo-list.db', help='Database file to load/store')
    parser.add_argument('--cleanup-time', default=12, type=int, help='Duration in hours after which finished items are removed')
    parser.add_argument('--issue-link-prefix', default=None, help='Prefix for links to bugtracker entries')

    args = parser.parse_args()

    gui = MainWindow(args)

    gui.show()
    sys.exit(app.exec_())
