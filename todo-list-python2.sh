#!/bin/sh

SCRIPT=$(readlink -f "$0")
SCRIPTPATH=`dirname "$SCRIPT"`

cd $SCRIPTPATH
python2 todo-list.py $@
