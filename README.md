# tdl
ToDo Lists as I had on paper extended by some GTD method (Getting Things Done [https://gettingthingsdone.com]) inspired features...

![alt text](tdl.png)

## Usage

```
>todo-list.py --help
usage: todo-list utility [-h] 
                         [--database DATABASE]
                         [--cleanup-time CLEANUP_TIME]
                         [--link [LINK ...]]
                         [--remote REMOTE]
                         [--issue-tab]

options:
  -h, --help            show this help message and exit
  --database DATABASE   Database file to load/store
  --cleanup-time CLEANUP_TIME
                        Duration in hours after which finished items are removed
  --link [LINK ...]     Pairs of links and trigger regex. The result of the trigger expression is inserted into the link.
                        E.g. for Jira: 'http://jira.local/browse/<TRIGGER>,([A-Z]+-[0-9]+)'
  --remote REMOTE       Directory to push and pull versions from. For backups and synching
  --issue-tab           Show special tab for URLs and mentioned issues

```

## Create and Close Items

Create a new item by double clicking the last line of a tab.
An item is closed by checking the checkbox at the left side. It will be removed from the list after `--cleanup-time` seconds.

## Hashtags and Tabs and Project Tabs

Hashtags are used to group items. The following tags have a special GTD smeaning
* #backlog items are only shown in backlog tab or if a specified date is reached
* #check items are only shown in check tab or if a specified date is reached
* #do marks next steps

Groups are visualized via tabs. The following special GTD tabs are shown as menu bar on the left side.
* *Inbox* shows items without any tag and #check items terminated today
* *Today* shows all items with termination date today or in the past
* *Next 7 Days* shows items, which termination date is within next 7 days, without today
* *Next Steps* shows all #do items with termination date today, or which are unterminated
* *Project* groups any custom tag in horizontal tabs, customizeable via *Filter* menu
* *Issues* shows all items with a valid issue tracker reference

Hidden special tabs, that can be shown temporary via main menu:
* The *All* tab shows alls items
* The *check* tab shows all items with a #check tag
* The *backlog* tab shows all items with #backlog tag

## Due Dates

You can add due dates to an item via following syntactic elements

* *@Xd* due to X days (e.g. *@3d*)
* *@d-m* due to date d.m. This is the default reprensentation, into all others are converted to. (e.g. *@24-12*)
* *@(mo|di|mi|do|fr|sa|so)* due to next (german) weekday (e.g. *@do*)

Due dates are used to sort the items in a tab, earliest at the top. Further, items with due dates are coloured.
* blue: item with a due date
* oragne: due date expires today
* red: due date is in the past

## Issue Tracker References

References to issue trackers can be added via the --link argument. It expects a list of pairs of a link with the `<TRIGGER>` keyword and a regex, used to search for triggers. The `<TRIGGER>` keyword will be replaced by the result of the regex search to create a link.

E.g
* *Redmine* via `--link "http://redmine.local/issues/<TRIGGER>,#([0-9]+)"`
* *Jira* via `--link "http://jira.local/browse/<TRIGGER>,([A-Z]+-[0-9]+)"`
* *Gerrit* via `--link "http://gerrit.local/#/c/<TRIGGER>,g([0-9]+)"`

The corresponding webpage is opended when you right click on the item.

## URL References

http(s) URLs are opened when you right click in the item.

## Sync to Remote Directory

If `--remote` is specified and points to an accesible directory, the database can be pushed to the remote location via menu entry `Remote/Push`. The last version in the remote directory can further by pulled via menu entry `Remote/Pull latest`.
This can be used to backup the databse and to synchronize several tdl instances.