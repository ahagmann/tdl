#!env python3

#
# todo-list
#
# https://github.com/ahagmann/tdl
#
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
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5 import QtWidgets
import time
import datetime
import re
import argparse
import json
import os
from functools import partial
import signal
import shutil
import glob


ROOT = os.path.abspath(os.path.dirname(__file__))


def debug(s):
    # print("DEBUG: %s" % s)
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
            if not (item.today or item.overdue):
                return False

        if ('check' in item.tags) and (self.tag != 'check'):
            if not (item.today or item.overdue):
                return False

        return self.tag in item.tags


class AllQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        return True


class UrlQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if 'backlog' in item.tags:
            if not (item.today or item.overdue):
                return False

        if 'check' in item.tags:
            if not (item.today or item.overdue):
                return False

        return len(item.urls) > 0


class InboxQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        if len(item.tags) == 0:
            return True

        if 'backlog' in item.tags and (item.today or item.overdue):
            return True

        if 'check' in item.tags and (item.today or item.overdue or item.due is None):
            return True

        return False


class TodayQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        return item.today or item.overdue


class Next7DaysQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return True

        return item.next_7_days


class AllWOEmptyQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return False

        return True


class ActiveWOEmptyQSortFilterProxyModel(SortQSortFilterProxyModelBase):
    def __init__(self, parent=None):
        SortQSortFilterProxyModelBase.__init__(self, parent)

    def filterAcceptsRow(self, source_row, source_parent):
        item = self.sourceModel().item(source_row)

        if item.empty is True:
            return False

        if 'backlog' in item.tags and not (item.today or item.overdue):
            return False

        if 'check' in item.tags and not (item.next_7_days or item.today or item.overdue):
            return False

        if item.checkState() == 2:
            return False

        return True


class ItemView(QtWidgets.QWidget):
    def __init__(self, model, filter_proxy_model, name, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        uic.loadUi('item_view.ui', self)

        self.name = name
        self.sourceModel = model

        self.view.setSpacing(0)

        self.model = filter_proxy_model
        self.model.setSourceModel(model)
        self.view.setModel(self.model)

        self.view.customContextMenuRequested.connect(self.openUrls)

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

    def openUrls(self, pos):
        index = self.view.indexAt(pos)
        source_index = self.model.mapToSource(index)
        item = self.sourceModel.item(source_index.row())
        if item:
            for url in item.urls:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


class Item(QtGui.QStandardItem):
    sequence_number = 0

    def __init__(self, link_configs, text='', done_timestamp=None):
        QtGui.QStandardItem.__init__(self, text)
        self.link_configs = link_configs
        self.empty = True
        self.done_timestamp = done_timestamp
        self.tags = []
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
        self.tags = [tag.lower() for tag in self.tags]

        # parse links
        self.urls = []
        for link, re_trigger in self.link_configs:
            for trigger in re.findall(re_trigger, self.text()):
                self.urls.append(link.replace('<TRIGGER>', trigger))

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
        self.overdue = False
        self.today = False
        self.next_7_days = False
        if len(due_dates) > 0:
            due_date = due_dates[0]
            year = datetime.datetime.now().year
            due_date_day = datetime.datetime.strptime(due_date, "%d-%m")
            due_date_day = due_date_day.replace(year=year)
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if today - due_date_day > datetime.timedelta(30):    # shift to next year if date is older than one past month
                due_date_day = due_date_day.replace(year=year + 1)

            self.due = time.mktime(due_date_day.timetuple())

            # set color and state for item including dates
            if self.checkState() != 2:
                diff = self.due - time.mktime(today.timetuple())
                if diff < 0:
                    brush.setColor(QtGui.QColor(255, 0, 0))
                    self.overdue = True
                elif diff < 3600 * 24:
                    brush.setColor(QtGui.QColor(255, 128, 0))
                    self.today = True
                elif diff < 3600 * 24 * 7:
                    brush.setColor(QtGui.QColor(0, 102, 204))
                    self.next_7_days = True
                else:
                    brush.setColor(QtGui.QColor(0, 102, 204))

        else:
            self.due = None

        self.setForeground(brush)

    def __str__(self):
        return "%s (%s, %s, %s)" % (self.text(), str(self.done_timestamp), str(self.tags), str(self.urls))


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, args, parent=None):
        super().__init__(parent)
        uic.loadUi('mainwindow.ui', self)

        self.do_not_store = False
        self.database_file = os.path.expanduser(args.database)
        self.database_temp_file = self.database_file + ".tmp"
        self.link_configs = args.link
        self.cleanup_time_h = args.cleanup_time
        self.remote = args.remote
        self.main_tabs = {}

        self.model = QtGui.QStandardItemModel(self)

        self.all_filter = AllWOEmptyQSortFilterProxyModel()
        self.all_filter.setSourceModel(self.model)
        self.active_filter = ActiveWOEmptyQSortFilterProxyModel()
        self.active_filter.setSourceModel(self.model)

        self.add_main_tab_item_view(self.model, InboxQSortFilterProxyModel(self), "Inbox")
        self.add_main_tab_item_view(self.model, TodayQSortFilterProxyModel(self), "Today")
        self.add_main_tab_item_view(self.model, Next7DaysQSortFilterProxyModel(self), "Next 7 Days")
        self.add_main_tab_item_view(self.model, TagQSortFilterProxyModel("do", self), "Next Steps")
        if args.issue_tab:
            self.add_main_tab_item_view(self.model, InboxQSortFilterProxyModel(self), "Issues")
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane {border: 0;}")
        self.add_main_tab_view(self.tabs, "Projects")
        self.add_main_tab_item_view(self.model, AllQSortFilterProxyModel(self), "All")
        self.add_main_tab_item_view(self.model, TagQSortFilterProxyModel("check", self), "Check")
        self.add_main_tab_item_view(self.model, TagQSortFilterProxyModel("backlog", self), "Backlog")

        self.status_bar = QtWidgets.QLabel()
        self.statusBar.addPermanentWidget(self.status_bar)

        self.load()
        self.add_empty_item()

        self.model.itemChanged.connect(self.on_item_changed)
        self.actionClose.triggered.connect(self.closeTab)
        self.actionReload.triggered.connect(self.reload)
        self.actionExit.triggered.connect(self.exit_request)
        self.actionPush.triggered.connect(lambda: self.remote_action("push"))
        self.actionPull.triggered.connect(lambda: self.remote_action("pull"))
        self.actionShowAll.triggered.connect(lambda: self.main_tab_changed(len(self.main_tabs) - 3))
        self.actionShowCheck.triggered.connect(lambda: self.main_tab_changed(len(self.main_tabs) - 2))
        self.actionShowBacklog.triggered.connect(lambda: self.main_tab_changed(len(self.main_tabs) - 1))

        icon = QtGui.QIcon(os.path.join(ROOT, 'icon.png'))
        self.sys_tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.sys_tray_icon.setIcon(icon)
        self.sys_tray_icon.setVisible(True)
        self.sys_tray_icon.activated.connect(self.tray_action)

        self.cleanup_timer = QtCore.QTimer(self)
        self.cleanup_timer.setInterval(10 * 60 * 1000)
        self.cleanup_timer.timeout.connect(self.cleanup)
        self.cleanup_timer.start()

        self.updateItemViews()

        color = self.palette().window().color()
        bg_color = "#%02x%02x%02x" % (color.red(), color.green(), color.blue())
        color = self.palette().highlight().color()
        hl_color = "#%02x%02x%02x" % (color.red(), color.green(), color.blue())

        self.mainTabsList.setStyleSheet("""
            QListWidget {
                background-color: %s;
                outline: 0;
            }
            QListWidget::item {
                padding-top: 10px;
                padding-bottom: 10px;
            }
            QListWidget::item:selected {
                background-color: %s;
                border: none;
            }
            """ % (bg_color, hl_color))

        self.mainTabsList.currentRowChanged.connect(self.main_tab_changed)
        self.mainTabsList.setCurrentRow(0)

    def main_tab_changed(self, tab):
        # show tab
        self.mainTabsStack.setCurrentIndex(tab)

        # enable/disable filter menue
        projects_tab_index = len(self.main_tabs) - 4
        self.menuFilter.setEnabled(tab == projects_tab_index)

        # show/hide "all", "check", and "backlog" tab
        for i in range(3):
            tab_index = len(self.main_tabs) - i - 1
            if tab == tab_index:
                self.mainTabsList.item(tab_index).setHidden(False)
                self.mainTabsList.setCurrentRow(tab_index)
            else:
                self.mainTabsList.item(tab_index).setHidden(True)

    def add_main_tab_item_view(self, model, filter_proxy_model, name):
        view = ItemView(model, filter_proxy_model, name)
        self.add_main_tab_view(view, name)

    def add_main_tab_view(self, view, name):
        self.mainTabsStack.insertWidget(len(self.main_tabs), view)
        list_item = QtWidgets.QListWidgetItem(name)
        self.mainTabsList.addItem(list_item)

        self.main_tabs[name] = {"list_item": list_item, "item_view": view}

    def add_empty_item(self):
        item = Item(self.link_configs)
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
            ret = QtWidgets.QMessageBox.warning(self, "Uups...", "Found a database temp file (%s).\nPress 'Ignore' to continue.\nPress 'Cancel' allows to continue in read only mode, to quit and check and solve this manually." % self.database_temp_file, buttons=QtGui.QMessageBox.Ignore | QtGui.QMessageBox.Cancel)
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
                        item = Item(self.link_configs, i['text'], i['done_timestamp'])
                        self.model.appendRow(item)

                    for i in db['tag_filter']:
                        self.addTagTab(i.lower())
                else:
                    raise "Unknown database version"

            except Exception as e:
                print("WARNING: Could not load database from '%s': %s" % (self.database_file, str(e)))
                sys.exit(1)
        else:
            print("WARNING: No database found at '%s'. Start with an empty database." % (self.database_file))

        self.updateMenu()
        self.updateItemViews()

    def reload(self):
        self.model.clear()
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self.load()
        self.add_empty_item()
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
            json_struct['tag_filter'].append(self.tabs.widget(i).name)

        s = json.dumps(json_struct, sort_keys=True, indent=4, separators=(',', ': '))
        with open(self.database_temp_file, 'w') as f:
            f.write(s)
        shutil.copy(self.database_temp_file, self.database_file)
        os.remove(self.database_temp_file)

    def remote_action(self, action):
        try:
            if self.remote is None:
                raise Exception("No remote specified")
            if not os.path.isdir(self.remote):
                raise Exception("Remote %s cannot be accesed" % self.remote)

            if action == "push":
                self.store()
                version_name = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_todo-list.db")
                shutil.copy2(self.database_file, os.path.join(self.remote, version_name))
                self.statusBar.showMessage("Pushed to %s" % version_name, 3000)

            if action == "pull":
                files = glob.glob(self.remote + "/*_todo-list.db")
                if len(files) == 0:
                    raise Exception("No database found in %s" % self.remote)
                files.sort()
                remote_file = files[-1]
                shutil.copy2(remote_file, self.database_file)
                self.reload()
                self.statusBar.showMessage("Pulled %s" % os.path.basename(remote_file), 3000)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error during %s" % action, str(e))

    def updateMenu(self):
        open_tabs = []
        for i in range(self.tabs.count()):
            open_tabs.append(self.tabs.widget(i).name)

        tags = []
        for i in range(self.model.rowCount()):
            for new_tag in self.model.item(i).tags:
                if new_tag not in open_tabs:
                    tags.append(new_tag)
        tags = sorted(list(set(tags)))

        self.menuAdd.clear()
        for tag in tags:
            action = QtWidgets.QAction(tag, self)
            self.menuAdd.addAction(action)
            action.triggered.connect(partial(self.addTagTab, tag))

    def updateItemViews(self):
        # update main tabs
        self.updateMainTabItemCount("Inbox")
        self.updateMainTabItemCount("Today")
        self.updateMainTabItemCount("Next 7 Days")
        self.updateMainTabItemCount("Next Steps")
        self.updateMainTabItemCount("Issues")
        self.updateMainTabItemCount("All")
        self.updateMainTabItemCount("Check")
        self.updateMainTabItemCount("Backlog")
        
        # update projects tab
        projects_item_count = 0
        for i in range(self.tabs.count()):
            self.tabs.widget(i).sort()
            c = self.tabs.widget(i).activeCount()
            n = self.tabs.widget(i).name
            label = "%s (%d)" % (n, c)
            self.tabs.setTabText(i, label)
            projects_item_count += c

        self.updateMainTabItemCount("Projects", projects_item_count)

        # update items
        for r in range(self.model.rowCount()):
            index = self.model.index(r, 0)
            item = self.model.itemFromIndex(index)
            item.updateState()

        # update main window
        self.status_bar.setText("%d/%d items" % (self.active_filter.rowCount(), self.all_filter.rowCount()))

    def updateMainTabItemCount(self, name, value=None):
        if name in self.main_tabs:
            if value is None:
                view = self.main_tabs[name]["item_view"]
                c = view.activeCount()
            else:
                c = value

            list_item = self.main_tabs[name]["list_item"]
            label = "%s (%d)" % (name, c)
            list_item.setText(label)

    def addTagTab(self, tag):
        filter = TagQSortFilterProxyModel(tag, self)
        tab = ItemView(self.model, filter, tag, self)
        self.tabs.addTab(tab, tag)

        self.updateItemViews()
        self.updateMenu()

    def closeTab(self):
        i = self.tabs.currentIndex()
        self.tabs.removeTab(i)
        self.updateMenu()
        self.updateItemViews()

    def closeEvent(self, event):
        self.store()
        super().closeEvent(event)

    def tray_action(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.hide()
            self.setGeometry(self.geometry())
            self.show()

    def exit_request(self, *args):
        self.sys_tray_icon.setVisible(False)
        self.close()


def link_argument(arg):
    ret = [str(x) for x in arg.split(',')]
    if len(ret) != 2:
        raise argparse.ArgumentTypeError("Expects a pair separated by ','")

    try:
        re.compile(ret[1])
    except Exception as e:
        raise argparse.ArgumentTypeError("Invalid regex: %s" % str(e))

    if '<TRIGGER>' not in ret[0]:
        raise argparse.ArgumentTypeError("<TRIGGER> keyword not found")

    return ret


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    parser = argparse.ArgumentParser("todo-list utility")
    parser.add_argument('--database', default='~/.todo-list.db', help='Database file to load/store')
    parser.add_argument('--cleanup-time', default=12, type=int, help='Duration in hours after which finished items are removed')
    parser.add_argument('--link', nargs='*', type=link_argument, default=[], help="Pairs of links and trigger regex. The result of the trigger expression is inserted into the link. E.g. for Jira: 'http://jira.local/browse/<TRIGGER>,([A-Z]+-[0-9]+)'")
    parser.add_argument('--remote', help='Directory to push and pull versions from. For backups and synching')
    parser.add_argument('--issue-tab', action='store_true', help='Show special tab for URLs and mentioned issues')

    args = parser.parse_args()

    # default links
    args.link.append(['<TRIGGER>', '(http.?://[^ ]+)'])

    gui = MainWindow(args)

    signal.signal(signal.SIGINT, gui.exit_request)
    signal.signal(signal.SIGTERM, gui.exit_request)

    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    gui.show()
    sys.exit(app.exec_())
