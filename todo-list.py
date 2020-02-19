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

try:
    from PyQt5 import sip
except ImportError:
    import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

import sys
try:
    from PyQt5 import QtCore, QtGui, uic
    from PyQt5.QtCore import QSortFilterProxyModel
    from PyQt5 import QtWidgets
except ImportError:
    from PyQt4 import QtCore, QtGui, uic
    from PyQt4.QtGui import QSortFilterProxyModel
    from PyQt4 import QtGui as QtWidgets
import time
import datetime
import re
import argparse
import json
import os
from functools import partial
import signal
import shutil


ROOT = os.path.abspath(os.path.dirname(__file__))


def debug(s):
    #print("DEBUG: %s" % s)
    pass


class SortQSortFilterProxyModelBase(QSortFilterProxyModel):
    def __init__(self, parent=None):
        QSortFilterProxyModel.__init__(self, parent)
        self.setDynamicSortFilter(True)

    def lessThan(self, index_a, index_b):
        item_a = self.sourceModel().itemFromIndex(index_a)
        item_b = self.sourceModel().itemFromIndex(index_b)

        if item_a.empty is True:
            return False

        if item_b.empty is True:
            return True

        if item_a.due is None and item_b.due is None:
            return item_b.sort_index > item_a.sort_index
        elif item_a.due is None and item_b.due is not None:
                return False
        elif item_a.due is not None and item_b.due is None:
                return True
        else:
            if item_b.due == item_a.due:
                return item_b.sort_index > item_a.sort_index
            else:
                return item_b.due > item_a.due


class TagQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, tag, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)
        self.tag = tag

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if ('backlog' in item.tags) and (self.tag != 'backlog'):
            return False

        return self.tag in item.tags


class IssueQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if 'backlog' in item.tags:
            return False

        return len(item.redmine_issues + item.jira_issues) > 0


class DueQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        return item.due is not None


class AllQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if 'backlog' in item.tags:
            return False

        return True


class Tab(QtWidgets.QWidget):
    def __init__(self, model, filter, name, redmine_issue_link_prefix, jira_issue_link_prefix, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        uic.loadUi('tab.ui', self)

        self.name = name
        self.sourceModel = model
        self.redmine_issue_link_prefix = redmine_issue_link_prefix
        self.jira_issue_link_prefix = jira_issue_link_prefix

        #self.view.viewport().setAutoFillBackground(False)

        if filter is None:
            self.model = AllQSortFilterProxyModel(self)
        elif filter == '_ISSUES':
            self.model = IssueQSortFilterProxyModel(self)
        elif filter == '_DUE':
            self.model = DueQSortFilterProxyModel(self)
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

    def sort(self):
        self.model.sort(0)

    def openIssue(self, pos):
        index = self.view.indexAt(pos)
        source_index = self.model.mapToSource(index)
        item = self.sourceModel.item(source_index.row())
        if item:
            if self.redmine_issue_link_prefix is not None:
                for issue in item.redmine_issues:
                    url = QtCore.QUrl(self.redmine_issue_link_prefix + issue)
                    QtGui.QDesktopServices.openUrl(url)
            if self.jira_issue_link_prefix is not None:
                for issue in item.jira_issues:
                    url = QtCore.QUrl(self.jira_issue_link_prefix + issue)
                    QtGui.QDesktopServices.openUrl(url)
            for url in item.urls:
                url = QtCore.QUrl(url)
                QtGui.QDesktopServices.openUrl(url)


class Item(QtGui.QStandardItem):
    sequence_number = 0

    def __init__(self, text='', done_timestamp=None):
        QtGui.QStandardItem.__init__(self, text)
        self.empty = True
        self.done_timestamp = done_timestamp
        self.tags = []
        self.redmine_issues = []
        self.jira_issues = []
        self.urls = []
        self.due = None
        self.sort_index = Item.sequence_number
        Item.sequence_number += 1
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

        # parse tags
        self.tags = re.findall(r'#([A-Za-z][A-Za-z0-9]*)', self.text())

        # parse issues
        self.redmine_issues = re.findall(r'#([0-9]+)', self.text())
        self.jira_issues = re.findall(r'([A-Z]+-[0-9]+)', self.text())
        self.urls = re.findall(r'(http.?://[^ ]+)', self.text())

        # replace due 'days' by due 'date'
        due_days = re.findall(r'@([0-9]+)d', self.text())
        if len(due_days) > 0:
            due_day = due_days[0]
            due_date = datetime.datetime.fromtimestamp(time.time() + int(due_day) * 3600 * 24).strftime("@%d-%m")
            self.setText(self.text().replace("@%sd" % due_day, due_date))

        # replace due 'weekdays' by due 'date'
        due_days = re.findall(r'@(mo|di|mi|do|fr|sa|so)', self.text(), re.IGNORECASE)
        if len(due_days) > 0:
            due_day = due_days[0]
            due_day_num = {'mo': 1, 'di': 2, 'mi': 3, 'do': 4, 'fr': 5, 'sa': 6, 'so': 0}[due_day.lower()]
            today_num = int(datetime.datetime.fromtimestamp(time.time()).strftime("%w"))
            day_diff = (due_day_num - today_num) % 7
            if day_diff == 0:
                day_diff = 7
            due_date = datetime.datetime.fromtimestamp(time.time() + day_diff * 3600 * 24).strftime("@%d-%m")
            self.setText(self.text().replace("@%s" % due_day, due_date))

        # parse dates
        due_dates = re.findall(r'@([0-9]+-[0-9]+)', self.text())
        brush = self.foreground()
        brush.setColor(QtGui.QColor(0, 0, 0))
        if len(due_dates) > 0:
            due_date = due_dates[0]
            year = datetime.datetime.now().year
            due_date_day = datetime.datetime.strptime(due_date, "%d-%m")
            due_date_day = due_date_day.replace(year=year)
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if today - due_date_day > datetime.timedelta(30):    # shift to next year if date is older than one past month
                due_date_day = due_date_day.replace(year=year + 1)

            self.due = time.mktime(due_date_day.timetuple())

            # set color for item including dates
            if self.checkState() != 2:
                diff = self.due - time.mktime(today.timetuple())
                if diff < 0:
                    brush.setColor(QtGui.QColor(255, 0, 0))
                elif diff < 3600 * 24:
                    brush.setColor(QtGui.QColor(255, 128, 0))
                else:
                    brush.setColor(QtGui.QColor(0, 102, 204))

        else:
            self.due = None

        self.setForeground(brush)

    def __str__(self):
        return "%s (%s, %s, %s)" % (self.text(), str(self.done_timestamp), str(self.tags), str(self.redmine_issues + self.jira_issues))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, args, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        uic.loadUi('mainwindow.ui', self)

        self.do_not_store = False
        self.database_file = os.path.expanduser(args.database)
        self.database_temp_file = self.database_file + ".tmp"
        self.redmine_issue_link_prefix = args.redmine_link_prefix
        self.jira_issue_link_prefix = args.jira_link_prefix
        self.cleanup_time_h = args.cleanup_time

        self.model = QtGui.QStandardItemModel(self)

        all_tab = Tab(self.model, None, 'All', self.redmine_issue_link_prefix, self.jira_issue_link_prefix, self)
        self.tabs.addTab(all_tab, "All")

        due_tab = Tab(self.model, '_DUE', 'Due', self.redmine_issue_link_prefix, self.jira_issue_link_prefix, self)
        self.tabs.addTab(due_tab, "Due")

        issue_tab = Tab(self.model, '_ISSUES', "Issues", self.redmine_issue_link_prefix, self.jira_issue_link_prefix, self)
        self.tabs.addTab(issue_tab, "Issues")

        self.load()
        self.add_empty_item()

        self.model.itemChanged.connect(self.on_item_changed)
        self.actionClose.triggered.connect(self.closeTab)

        icon = QtGui.QIcon(os.path.join(ROOT, 'icon.png'))
        self.sys_tray_icon = QtWidgets.QSystemTrayIcon(self)
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
        self.updateItemViews()

    def cleanup(self):
        duration = self.cleanup_time_h * 60 * 60
        for i in reversed(range(self.model.rowCount())):
            item = self.model.item(i)
            if item.done_timestamp:
                if item.done_timestamp < (time.time() - duration):
                    self.model.removeRow(item.row())
                    debug("remove %d" % i)

        self.store()
        self.updateItemViews()

    def load(self):
        if os.path.exists(self.database_temp_file):
            ret = QtWidgets.QMessageBox.warning(self, "Uups...", "Found a database temp file (%s).\nPress 'Ignore' to continue.\nPress 'Cancel' allows to continue in read only mode, to quit and check and solve this manually." % self.database_temp_file, buttons = QtGui.QMessageBox.Ignore | QtGui.QMessageBox.Cancel)
            if ret == QtWidgets.QMessageBox.Cancel:
                self.do_not_store = True

                p = self.palette()
                p.setColor(self.backgroundRole(), QtCore.Qt.red)
                self.setPalette(p)
                self.setWindowTitle(self.windowTitle() + ' (Read only)')

        elif os.path.exists(self.database_file):
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
                sys.exit(1)
        else:
            print("WARNING: No database found at '%s'. Start with an empty database." % (self.database_file))


        self.updateMenu()
        self.updateItemViews()

    def store(self):
        if self.do_not_store is True:
            return

        json_struct = {'version': "1.0", 'database': [], 'tag_filter': []}

        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.empty is False:
                json_struct['database'].append({'text': item.text(), 'done_timestamp': item.done_timestamp})

        for i in range(self.tabs.count()):
            if i > 2:
                json_struct['tag_filter'].append(self.tabs.widget(i).name)

        s = json.dumps(json_struct, sort_keys=True, indent=4, separators=(',', ': '))
        with open(self.database_temp_file, 'w') as f:
            f.write(s)
        shutil.copy(self.database_temp_file, self.database_file)
        os.remove(self.database_temp_file)

    def updateMenu(self):
        tags = []
        for i in range(self.model.rowCount()):
            tags += self.model.item(i).tags
        tags = sorted(list(set(tags)))

        self.menuAdd.clear()
        for tag in tags:
            action = QtWidgets.QAction(tag, self)
            self.menuAdd.addAction(action)
            action.triggered.connect(partial(self.addTagTab, tag))

    def updateItemViews(self):
        for i in range(self.tabs.count()):
            self.tabs.widget(i).sort()
            c = self.tabs.widget(i).activeCount()
            n = self.tabs.widget(i).name
            label = "%s (%d)" % (n, c)
            self.tabs.setTabText(i, label)

        # update items
        for r in range(self.model.rowCount()):
            index = self.model.index(r, 0)
            item = self.model.itemFromIndex(index)
            #name = self.model.data(index)
            item.updateState()

    def addTagTab(self, tag):
        tab = Tab(self.model, tag, tag, self.redmine_issue_link_prefix, self.jira_issue_link_prefix, self)
        self.tabs.addTab(tab, tag)

        self.updateItemViews()

    def closeTab(self):
        i = self.tabs.currentIndex()
        if i > 2:
            self.tabs.removeTab(i)

    def closeEvent(self, event):
        QtWidgets.QMainWindow.closeEvent(self, event)
        self.store()

    def tray_action(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.hide()
            self.setGeometry(self.geometry())
            self.show()

    def exit_request(self, *args):
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    parser = argparse.ArgumentParser("todo-list utility")
    parser.add_argument('--database', default='~/.todo-list.db', help='Database file to load/store')
    parser.add_argument('--cleanup-time', default=12, type=int, help='Duration in hours after which finished items are removed')
    parser.add_argument('--redmine-link-prefix', '--issue-link-prefix', default=None, help='Prefix for links to Redmine bugtracker entries')
    parser.add_argument('--jira-link-prefix', default=None, help='Prefix for links to Jira bugtracker entries')

    args = parser.parse_args()

    gui = MainWindow(args)

    signal.signal(signal.SIGINT, gui.exit_request)
    signal.signal(signal.SIGTERM, gui.exit_request)

    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    gui.show()
    sys.exit(app.exec_())
