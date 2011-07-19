
#
# This file is to be included with '.'
#

BASEDIR="`pwd | sed 's;/cx/.*;/cx;'`/lib"

[ -z "`echo $PYTHONPATH | grep cxnet`" ] && export PYTHONPATH="$PYTHONPATH:$BASEDIR/cxnet"
[ -z "`echo $PYTHONPATH | grep py9p`" ]  && export PYTHONPATH="$PYTHONPATH:$BASEDIR/py9p"
