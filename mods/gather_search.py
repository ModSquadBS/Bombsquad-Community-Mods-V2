from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, cast

import _ba
import ba

if TYPE_CHECKING:
    from typing import Any, Optional, Tuple, Dict, List, Union, Callable
import bastd.ui.gather as gather

searchText=None
checkBoxBool=False
textModified=False
class Gather(gather.GatherWindow):
    def _update_internet_tab(self) -> None:
        global searchText,textModified
        def updatepartylist():
            self._internet_join_last_refresh_time = now
            self._first_public_party_list_rebuild_time=ba.time(ba.TimeType.REAL)+1
            app = ba.app
            _ba.add_transaction(
                    {
                        'type': 'PUBLIC_PARTY_QUERY',
                        'proto': app.protocol_version,
                        'lang': app.language
                    },
            callback=ba.WeakCall(self._on_public_party_query_result))
            _ba.run_transactions()
        def checkBox(val):
            global checkBoxBool
            checkBoxBool=bool(val)
            updatepartylist()

        if not searchText:
            widgetInstalled=True
            c_width = self._scroll_width
            c_height = self._scroll_height - 20
            v = c_height - 30

            searchText = txt = ba.textwidget(
                parent=self._tab_container,
                position=(c_width * 0.5 + 250, v + 105),
                color=ba.app.ui.title_color,
                scale=1.3,
                size=(150, 30),
                maxwidth=145,
                h_align='left',
                v_align='center',
                click_activate=True,
                selectable=True,
                autoselect=True,
                on_activate_call=lambda: self._set_internet_tab(
                    'host', playsound=True),
                editable=True,
                text='')
            ba.textwidget(
                parent=self._tab_container,
                position=(c_width * 0.5 + 125, v + 122),
                color=ba.app.ui.title_color,
                scale=1.1,
                size=(0,0),
                h_align='left',
                v_align='center',
                on_activate_call=lambda: self._set_internet_tab(
                    'host', playsound=True),
                text='Search:')
            ba.checkboxwidget(
                    parent=self._tab_container,
                    text="Case-Sensitive",
                    position=(c_width * 0.5 + 125, v + 135),
                    color=ba.app.ui.title_color,
                    textcolor=ba.app.ui.title_color,
                    size=(50,50),
                    scale=1,
                    value=False,
                    on_value_change_call=checkBox
                )
        
        # pylint: disable=too-many-statements

        # Special case: if a party-queue window is up, don't do any of this
        # (keeps things smoother).
        if ba.app.ui.have_party_queue_window:
            return
        # If we've got a party-name text widget, keep its value plugged
        # into our public host name.
        text = self._internet_host_name_text
        if text:
            name = cast(str,
                        ba.textwidget(query=self._internet_host_name_text))
            _ba.set_public_party_name(name)

        # Show/hide the lock icon depending on if we've got pro.
        icon = self._internet_lock_icon
        if icon:
            if self._is_internet_locked():
                ba.imagewidget(edit=icon, opacity=0.5)
            else:
                ba.imagewidget(edit=icon, opacity=0.0)

        if self._internet_tab == 'join':
            now = ba.time(ba.TimeType.REAL)
            if (now - self._internet_join_last_refresh_time > 0.001 *
                    _ba.get_account_misc_read_val('pubPartyRefreshMS', 10000)) :
                updatepartylist()
            search_text=cast(str, ba.textwidget(query=searchText))

            if search_text!='':

                textModified=True
                x=[]
                if not checkBoxBool:
                    search_text=search_text.lower()
                    for i in self._public_parties:
                        if not search_text in self._public_parties[i]['name'].lower():
                            x.append(i)
                else:
                    for i in self._public_parties:
                        if not search_text in self._public_parties[i]['name']:
                            x.append(i)
                
                for i in x:
                    del self._public_parties[i]
                self._first_public_party_list_rebuild_time=ba.time(ba.TimeType.REAL)+1
                self._rebuild_public_party_list()


            else:
                if textModified:
                    updatepartylist()
                    
                    textModified=False
            # Go through our existing public party entries firing off pings
            # for any that have timed out.
            for party in list(self._public_parties.values()):
                if (party['next_ping_time'] <= now
                        and ba.app.ping_thread_count < 15) :

                    # Make sure to fully catch up and not to multi-ping if
                    # we're way behind somehow.
                    while party['next_ping_time'] <= now:
                        # Crank the interval up for high-latency parties to
                        # save us some work.
                        mult = 1
                        if party['ping'] is not None:
                            mult = (10 if party['ping'] > 300 else
                                    5 if party['ping'] > 150 else 2)
                        party[
                            'next_ping_time'] += party['ping_interval'] * mult

                    class PingThread(threading.Thread):
                        """Thread for sending out pings."""

                        def __init__(self, address: str, port: int,
                                     call: Callable[[str, int, Optional[int]],
                                                    Optional[int]]):
                            super().__init__()
                            self._address = address
                            self._port = port
                            self._call = call

                        def run(self) -> None:
                            # pylint: disable=too-many-branches
                            ba.app.ping_thread_count += 1
                            try:
                                import socket
                                from ba.internal import get_ip_address_type
                                socket_type = get_ip_address_type(
                                    self._address)
                                sock = socket.socket(socket_type,
                                                     socket.SOCK_DGRAM)
                                sock.connect((self._address, self._port))

                                accessible = False
                                starttime = time.time()

                                # Send a few pings and wait a second for
                                # a response.
                                sock.settimeout(1)
                                for _i in range(3):
                                    sock.send(b'\x0b')
                                    result: Optional[bytes]
                                    try:
                                        # 11: BA_PACKET_SIMPLE_PING
                                        result = sock.recv(10)
                                    except Exception:
                                        result = None
                                    if result == b'\x0c':
                                        # 12: BA_PACKET_SIMPLE_PONG
                                        accessible = True
                                        break
                                    time.sleep(1)
                                sock.close()
                                ping = int((time.time() - starttime) * 1000.0)
                                ba.pushcall(ba.Call(
                                    self._call, self._address, self._port,
                                    ping if accessible else None),
                                            from_other_thread=True)
                            except ConnectionRefusedError:
                                # Fine, server; sorry we pinged you. Hmph.
                                pass
                            except OSError as exc:
                                import errno

                                # Ignore harmless errors.
                                if exc.errno in {
                                        errno.EHOSTUNREACH,
                                        errno.ENETUNREACH,
                                }:
                                    pass
                                elif exc.errno == 10022:
                                    # Windows 'invalid argument' error.
                                    pass
                                elif exc.errno == 10051:
                                    # Windows 'a socket operation was attempted
                                    # to an unreachable network' error.
                                    pass
                                elif exc.errno == errno.EADDRNOTAVAIL:
                                    if self._port == 0:
                                        # This has happened. Ignore.
                                        pass
                                    elif ba.do_once():
                                        print(
                                            f'Got EADDRNOTAVAIL on gather ping'
                                            f' for addr {self._address}'
                                            f' port {self._port}.')
                                else:
                                    ba.print_exception(
                                        f'Error on gather ping '
                                        f'(errno={exc.errno})',
                                        once=True)
                            except Exception:
                                ba.print_exception('Error on gather ping',
                                                   once=True)
                            ba.app.ping_thread_count -= 1

                    PingThread(party['address'], party['port'],
                               ba.WeakCall(self._ping_callback)).start()
# ba_meta require api 6
# ba_meta export plugin
class Plugin(ba.Plugin):
	def on_app_launch(self):
		gather.GatherWindow._update_internet_tab=Gather._update_internet_tab
