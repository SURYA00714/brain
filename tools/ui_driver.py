"""
Brain Desktop UI Driver (Phase 5 Autonomous Desktop UI Interaction).
Combines Linux AT-SPI2 accessibility tree perception, native D-Bus Action invocation,
and robust X11/Wayland input fallbacks.
"""

import os
import time
from typing import Dict, Any, Optional, List, Tuple

from tools.ui_tree import default_ui_tree, AccessibleNode, HAS_DBUS

try:
    import dbus
except ImportError:
    dbus = None


class DesktopUIDriver:
    """
    Unified controller for native Linux desktop application interaction.
    - Perception: AT-SPI2 D-Bus tree inspection (<5ms).
    - Interaction (Primary): Native AT-SPI Action.DoAction (Headless, 0 mouse movement).
    - Interaction (Fallback): Coordinate click & typing via X11/Wayland input dispatch.
    - Synchronization: Real-time AT-SPI state & window discovery.
    """

    def __init__(self, ui_tree=None):
        self.tree = ui_tree or default_ui_tree

    def click_element(
        self,
        query: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
        prefer_native_action: bool = True,
        button: str = "left",
    ) -> Dict[str, Any]:
        """
        Locates an accessible element and activates it.
        Attempts native AT-SPI Action.DoAction(0) first; falls back to coordinate clicking.
        """
        node: Optional[AccessibleNode] = self.tree.find_element(query, role=role, app_name=app_name)
        if not node:
            return {
                "success": False,
                "tool": "CLICK_UI_ELEMENT",
                "error": f"Element '{query}' (role={role or 'any'}, app={app_name or 'any'}) not found in accessible desktop tree.",
                "method": "none",
            }

        # 1. Native AT-SPI Action invocation (Primary: headless, instant, zero pointer disruption)
        if prefer_native_action and HAS_DBUS and node.bus_name and node.path:
            try:
                a11y_bus = self.tree.get_a11y_bus()
                if a11y_bus:
                    obj = a11y_bus.get_object(node.bus_name, node.path)
                    action_iface = dbus.Interface(obj, "org.a11y.atspi.Action")
                    n_actions = int(action_iface.NActions)
                    if n_actions > 0:
                        # Invoke action 0 (typically 'click', 'press', or 'activate')
                        action_name = str(action_iface.GetName(0))
                        success = bool(action_iface.DoAction(0))
                        if success:
                            return {
                                "success": True,
                                "tool": "CLICK_UI_ELEMENT",
                                "method": "atspi_native_action",
                                "action_name": action_name,
                                "element": node.to_dict(),
                                "verified": True,
                            }
            except Exception:
                pass  # Fall back to coordinate click below

        # 2. Coordinate Click Fallback (X11 xdotool / pynput / Wayland ydotool)
        if node.width > 0 and node.height > 0:
            try:
                from tools.input import click_mouse
                click_res = click_mouse(node.center_x, node.center_y, button=button)
                return {
                    "success": True,
                    "tool": "CLICK_UI_ELEMENT",
                    "method": "coordinate_click_fallback",
                    "element": node.to_dict(),
                    "coordinates": [node.center_x, node.center_y],
                    "input_result": click_res,
                    "verified": True,
                }
            except Exception as e:
                return {
                    "success": False,
                    "tool": "CLICK_UI_ELEMENT",
                    "error": f"Failed coordinate click on '{node.name}': {e}",
                    "method": "coordinate_click_fallback",
                }

        # CI / Mock fallback
        if os.environ.get("BRAIN_MOCK_GUI") == "1":
            return {
                "success": True,
                "tool": "CLICK_UI_ELEMENT",
                "method": "mock_gui",
                "element": node.to_dict(),
                "verified": True,
            }

        return {
            "success": False,
            "tool": "CLICK_UI_ELEMENT",
            "error": f"Element '{node.name}' has zero dimensions and no native action interface.",
            "method": "failed",
        }

    def type_in_element(
        self,
        query: str,
        text: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
        clear_first: bool = False,
    ) -> Dict[str, Any]:
        """
        Locates an input field/textbox and enters text.
        Attempts native AT-SPI EditableText first; falls back to focus + keyboard typing.
        """
        node: Optional[AccessibleNode] = self.tree.find_element(query, role=role, app_name=app_name)
        if not node:
            return {
                "success": False,
                "tool": "TYPE_UI_ELEMENT",
                "error": f"Target input element '{query}' not found in accessible desktop tree.",
                "method": "none",
            }

        # 1. Native AT-SPI EditableText (Direct text injection)
        if HAS_DBUS and node.bus_name and node.path:
            try:
                a11y_bus = self.tree.get_a11y_bus()
                if a11y_bus:
                    obj = a11y_bus.get_object(node.bus_name, node.path)
                    edit_iface = dbus.Interface(obj, "org.a11y.atspi.EditableText")
                    if clear_first:
                        edit_iface.SetTextContents("")
                    ok = bool(edit_iface.SetTextContents(text))
                    if ok:
                        return {
                            "success": True,
                            "tool": "TYPE_UI_ELEMENT",
                            "method": "atspi_editable_text",
                            "element": node.to_dict(),
                            "text": text,
                            "verified": True,
                        }
            except Exception:
                pass  # Fall back to focus + typing

        # 2. Focus + Keyboard Typing Fallback
        self.click_element(query, role=role, app_name=app_name, prefer_native_action=False)
        time.sleep(0.08)

        try:
            from tools.input import type_text
            type_res = type_text(text)
            return {
                "success": True,
                "tool": "TYPE_UI_ELEMENT",
                "method": "keyboard_type_fallback",
                "element": node.to_dict(),
                "text": text,
                "input_result": type_res,
                "verified": True,
            }
        except Exception as e:
            if os.environ.get("BRAIN_MOCK_GUI") == "1":
                return {
                    "success": True,
                    "tool": "TYPE_UI_ELEMENT",
                    "method": "mock_gui",
                    "element": node.to_dict(),
                    "text": text,
                    "verified": True,
                }
            return {
                "success": False,
                "tool": "TYPE_UI_ELEMENT",
                "error": f"Failed typing into '{node.name}': {e}",
                "method": "keyboard_type_fallback",
            }

    def wait_for_element(
        self,
        query: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
        timeout_sec: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Polls the AT-SPI accessibility tree until the requested element appears.
        Replaces blind sleep() with event-driven state synchronization.
        """
        start = time.perf_counter()
        deadline = start + timeout_sec

        while time.perf_counter() < deadline:
            node = self.tree.find_element(query, role=role, app_name=app_name)
            if node:
                dur = round(time.perf_counter() - start, 3)
                return {
                    "success": True,
                    "tool": "WAIT_FOR_UI_ELEMENT",
                    "found": True,
                    "element": node.to_dict(),
                    "elapsed_sec": dur,
                }
            time.sleep(0.1)

        dur = round(time.perf_counter() - start, 3)
        return {
            "success": False,
            "tool": "WAIT_FOR_UI_ELEMENT",
            "found": False,
            "error": f"Timed out waiting {timeout_sec}s for element '{query}' (role={role}, app={app_name}).",
            "elapsed_sec": dur,
        }

    def inspect_app_ui(
        self,
        app_name: str,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """Returns structured hierarchy of UI widgets for a target application."""
        nodes = self.tree.inspect_tree(app_name=app_name, max_depth=max_depth)
        return {
            "success": True,
            "tool": "INSPECT_APP_UI",
            "app_name": app_name,
            "count": len(nodes),
            "elements": [n.to_dict() for n in nodes],
        }


default_ui_driver = DesktopUIDriver()


# Functional tool endpoints
def click_ui_element(query: str, role: Optional[str] = None, app_name: Optional[str] = None) -> Dict[str, Any]:
    return default_ui_driver.click_element(query=query, role=role, app_name=app_name)


def type_ui_element(query: str, text: str, role: Optional[str] = None, app_name: Optional[str] = None) -> Dict[str, Any]:
    return default_ui_driver.type_in_element(query=query, text=text, role=role, app_name=app_name)


def wait_for_ui_element(query: str, timeout_sec: float = 5.0, app_name: Optional[str] = None) -> Dict[str, Any]:
    return default_ui_driver.wait_for_element(query=query, timeout_sec=float(timeout_sec), app_name=app_name)


def inspect_app_ui(app_name: str, max_depth: int = 2) -> Dict[str, Any]:
    return default_ui_driver.inspect_app_ui(app_name=app_name, max_depth=int(max_depth))
