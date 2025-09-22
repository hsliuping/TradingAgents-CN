# LICENSE AGREEMENT FOR MATPLOTLIB 1.2.0
# --------------------------------------
#
# 1. This LICENSE AGREEMENT is between John D. Hunter ("JDH"), and the
# Individual or Organization ("Licensee") accessing and otherwise using
# matplotlib software in source or binary form and its associated
# documentation.
#
# 2. Subject to the terms and conditions of this License Agreement, JDH
# hereby grants Licensee a nonexclusive, royalty-free, world-wide license
# to reproduce, analyze, test, perform and/or display publicly, prepare
# derivative works, distribute, and otherwise use matplotlib 1.2.0
# alone or in any derivative version, provided, however, that JDH's
# License Agreement and JDH's notice of copyright, i.e., "Copyright (c)
# 2002-2011 John D. Hunter; All Rights Reserved" are retained in
# matplotlib 1.2.0 alone or in any derivative version prepared by
# Licensee.
#
# 3. In the event Licensee prepares a derivative work that is based on or
# incorporates matplotlib 1.2.0 or any part thereof, and wants to
# make the derivative work available to others as provided herein, then
# Licensee hereby agrees to include in any such work a brief summary of
# the changes made to matplotlib 1.2.0.
#
# 4. JDH is making matplotlib 1.2.0 available to Licensee on an "AS
# IS" basis.  JDH MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
# IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, JDH MAKES NO AND
# DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
# FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF MATPLOTLIB 1.2.0
# WILL NOT INFRINGE ANY THIRD PARTY RIGHTS.
#
# 5. JDH SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF MATPLOTLIB
# 1.2.0 FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR
# LOSS AS A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING
# MATPLOTLIB 1.2.0, OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF
# THE POSSIBILITY THEREOF.

# 6. This License Agreement will automatically terminate upon a material
# breach of its terms and conditions.
#
# 7. Nothing in this License Agreement shall be deemed to create any
# relationship of agency, partnership, or joint venture between JDH and
# Licensee.  This License Agreement does not grant permission to use JDH
# trademarks or trade name in a trademark sense to endorse or promote
# products or services of Licensee, or any third party.
#
# 8. By copying, installing or otherwise using matplotlib 1.2.0,
# Licensee agrees to be bound by the terms and conditions of this License
# Agreement.

# CHANGES
# The original MultiCursor plots all horizontal lines at the same time
# The modified version plots only the horizontal line in the axis in which the
# motion event takes place
#
# The original MultiCursos uses the ylimit of the las passed axis, to calculate
# the mid point of the axis. which creates a huge distorsion if all axis don't
# have the same y dimensions
#
# The modified version uses the y limits of each axis to calculate the initial
# position of each line avoiding the distorsion

from ..utils.py3 import zip

class Widget(object):
    """
    Abstract base class for GUI neutral widgets
    """
    drawon = True
    eventson = True
    _active = True

    def set_active(self, active):
        """Set whether the widget is active.
        """
        self._active = active

    def get_active(self):
        """Get whether the widget is active.
        """
        return self._active

    # set_active is overriden by SelectorWidgets.
    active = property(get_active, lambda self, active: self.set_active(active),
                      doc="Is the widget active?")

    def ignore(self, event):
        """Return True if event should be ignored.
        This method (or a version of it) should be called at the beginning
        of any event callback.
        """
        return not self.active


class MultiCursor(Widget):
    """
    Provide a vertical (default) and/or horizontal line cursor shared between
    multiple axes.

    For the cursor to remain responsive you much keep a reference to
    it.

    Example usage::

        from matplotlib.widgets import MultiCursor
        from pylab import figure, show, np

        t = np.arange(0.0, 2.0, 0.01)
        s1 = np.sin(2*np.pi*t)
        s2 = np.sin(4*np.pi*t)
        fig = figure()
        ax1 = fig.add_subplot(211)
        ax1.plot(t, s1)


        ax2 = fig.add_subplot(212, sharex=ax1)
        ax2.plot(t, s2)

        multi = MultiCursor(fig.canvas, (ax1, ax2), color='r', lw=1,
                            horizOn=False, vertOn=True)
        show()

    """
    def __init__(self, canvas, axes, useblit=True,
                 horizOn=False, vertOn=True,
                 horizMulti=False, vertMulti=True,
                 horizShared=True, vertShared=False,
                 **lineprops):

        self.canvas = canvas
        self.axes = axes
        self.horizOn = horizOn
        self.vertOn = vertOn
        self.horizMulti = horizMulti
        self.vertMulti = vertMulti

        self.visible = True
        self.useblit = useblit and self.canvas.supports_blit
        self.background = None
        self.needclear = False

        if self.useblit:
            lineprops['animated'] = True

        self.vlines = []
        if vertOn:
            xmin, xmax = axes[-1].get_xlim()
            xmid = 0.5 * (xmin + xmax)

            for ax in axes:
                if not horizShared:
                    xmin, xmax = ax.get_xlim()
                    xmid = 0.5 * (xmin + xmax)

                vline = ax.axvline(xmid, visible=False, **lineprops)
                self.vlines.append(vline)

        self.hlines = []
        if horizOn:
            ymin, ymax = axes[-1].get_ylim()
            ymid = 0.5 * (ymin + ymax)

            for ax in axes:
                if not vertShared:
                    ymin, ymax = ax.get_ylim()
                    ymid = 0.5 * (ymin + ymax)

                hline = ax.axhline(ymid, visible=False, **lineprops)
                self.hlines.append(hline)

        self.connect()

    def connect(self):
        """connect events"""
        self._cidmotion = self.canvas.mpl_connect('motion_notify_event',
                                                  self.onmove)
        self._ciddraw = self.canvas.mpl_connect('draw_event', self.clear)

    def disconnect(self):
        """disconnect events"""
        self.canvas.mpl_disconnect(self._cidmotion)
        self.canvas.mpl_disconnect(self._ciddraw)

    def clear(self, event):
        """clear the cursor"""
        if self.ignore(event):
            return
        if self.useblit:
            self.background = (
                self.canvas.copy_from_bbox(self.canvas.figure.bbox))
        for line in self.vlines + self.hlines:
            line.set_visible(False)

    def onmove(self, event):
        if self.ignore(event):
            return
        if event.inaxes is None:
            return
        if not self.canvas.widgetlock.available(self):
            return
        self.needclear = True
        if not self.visible:
            return
        if self.vertOn:
            for line in self.vlines:
                visible = self.visible
                if not self.vertMulti:
                    visible = visible and line.axes == event.inaxes

                if visible:
                    line.set_xdata((event.xdata, event.xdata))
                    line.set_visible(visible)
        if self.horizOn:
            for line in self.hlines:
                visible = self.visible
                if not self.horizMulti:
                    visible = visible and line.axes == event.inaxes
                if visible:
                    line.set_ydata((event.ydata, event.ydata))
                    line.set_visible(self.visible)
        self._update(event)

    def _update(self, event):
        if self.useblit:
            if self.background is not None:
                self.canvas.restore_region(self.background)
            if self.vertOn:
                for ax, line in zip(self.axes, self.vlines):
                    if self.vertMulti or event.inaxes == line.axes:
                        ax.draw_artist(line)

            if self.horizOn:
                for ax, line in zip(self.axes, self.hlines):
                    if self.horizMulti or event.inaxes == line.axes:
                        ax.draw_artist(line)
            self.canvas.blit(self.canvas.figure.bbox)
        else:
            self.canvas.draw_idle()

class MultiCursor2(Widget):
    """
    Provide a vertical (default) and/or horizontal line cursor shared between
    multiple axes.
    For the cursor to remain responsive you much keep a reference to
    it.
    Example usage::
        from matplotlib.widgets import MultiCursor
        from pylab import figure, show, np
        t = np.arange(0.0, 2.0, 0.01)
        s1 = np.sin(2*np.pi*t)
        s2 = np.sin(4*np.pi*t)
        fig = figure()
        ax1 = fig.add_subplot(211)
        ax1.plot(t, s1)
        ax2 = fig.add_subplot(212, sharex=ax1)
        ax2.plot(t, s2)
        multi = MultiCursor(fig.canvas, (ax1, ax2), color='r', lw=1,
                            horizOn=False, vertOn=True)
        show()
    """
    def __init__(self, canvas, axes, useblit=True, horizOn=False, vertOn=True,
                 **lineprops):

        self.canvas = canvas
        self.axes = axes
        self.horizOn = horizOn
        self.vertOn = vertOn

        xmin, xmax = axes[-1].get_xlim()
        xmid = 0.5 * (xmin + xmax)

        self.visible = True
        self.useblit = useblit and self.canvas.supports_blit
        self.background = None
        self.needclear = False

        if self.useblit:
            lineprops['animated'] = True

        if vertOn:
            self.vlines = [ax.axvline(xmid, visible=False, **lineprops)
                           for ax in axes]
        else:
            self.vlines = []

        if horizOn:
            self.hlines = []
            for ax in axes:
                ymin, ymax = ax.get_ylim()
                ymid = 0.5 * (ymin + ymax)
                hline = ax.axhline(ymid, visible=False, **lineprops)
                self.hlines.append(hline)
        else:
            self.hlines = []

        self.connect()

    def connect(self):
        """connect events"""
        self._cidmotion = self.canvas.mpl_connect('motion_notify_event',
                                                  self.onmove)
        self._ciddraw = self.canvas.mpl_connect('draw_event', self.clear)

    def disconnect(self):
        """disconnect events"""
        self.canvas.mpl_disconnect(self._cidmotion)
        self.canvas.mpl_disconnect(self._ciddraw)

    def clear(self, event):
        """clear the cursor"""
        if self.ignore(event):
            return
        if self.useblit:
            self.background = (
                self.canvas.copy_from_bbox(self.canvas.figure.bbox))
        for line in self.vlines + self.hlines:
            line.set_visible(False)

    def onmove(self, event):
        if self.ignore(event):
            return
        if event.inaxes is None:
            return

        if not self.canvas.widgetlock.available(self):
            return
        self.needclear = True
        if not self.visible:
            return
        if self.vertOn:
            for line in self.vlines:
                visible = True or line.axes == event.inaxes
                line.set_xdata((event.xdata, event.xdata))
                line.set_visible(visible)
        if self.horizOn:
            for line in self.hlines:
                visible = line.axes == event.inaxes
                line.set_ydata((event.ydata, event.ydata))
                line.set_visible(visible)
        self._update(event)

    def _update(self, event):
        if self.useblit:
            if self.background is not None:
                self.canvas.restore_region(self.background)
            if self.vertOn:
                for ax, line in zip(self.axes, self.vlines):
                    ax.draw_artist(line)
            if self.horizOn:
                for ax, line in zip(self.axes, self.hlines):
                    ax.draw_artist(line)
            self.canvas.blit(self.canvas.figure.bbox)
        else:
            self.canvas.draw_idle()
