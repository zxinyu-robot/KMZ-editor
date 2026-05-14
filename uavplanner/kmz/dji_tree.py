# -*- coding: utf-8 -*-
# ------------------------------------------------------------ #
# Description: 大疆 WPML/KML 同构树（XML 与 dict 双向转换）
# Author:      zxinyu
# Version:     1.0
# Time:        2026-02-11
# Copyright:   (c) 2025 zxinyu. All rights reserved.
# ------------------------------------------------------------ #

"""大疆 WPML + KML 同构树：XML ↔ JSON（dict）双向转换。

节点形状（与 ``dji_kmz_tree_spec.md`` 一致）::

    {
      "tag": "kml" | "Document" | "wpml:missionConfig" | ...,
      "attrs": { "xmlns": "...", "xmlns:wpml": "...", ... },   # 可选；不含 __head
      "head": "\\n  ",                                         # 可选；第一个子元素前的原文本
      "body": "叶文本" | [ 子节点, ... ],                       # 叶为 str；枝为 list
      "tail": "\\n"                                            # 可选，缺省 ""；该元素闭合后、下一兄弟前的 tail
    }

* ``coordinates`` 的测绘值在 **叶** 上放在 ``body``（str），不拆分数组。
* WPML 元素 ``tag`` 恒为 ``wpml:`` + 本地名；KML 默认命名空间元素 **无前缀**。

另提供 **KML 形嵌套 JSON**（与 ``template.kml`` 层级一致）：根对象单键 ``kml``，其下子元素名为键；
声明写在 ``@xmlns``、``@xmlns:wpml``；叶为字符串；同名兄弟为 **数组**。见 ``node_to_kml_like`` / ``kml_like_to_node``。
"""

from __future__ import annotations

import copy
import zipfile
from typing import Any, Dict, List, Optional

from lxml import etree

KML_NS = "http://www.opengis.net/kml/2.2"
WPML_NS = "http://www.dji.com/wpmz/1.0.6"
XMLNS_NS = "http://www.w3.org/2000/xmlns/"

DjiNode = Dict[str, Any]


def _tag_to_str(el: etree._Element) -> str:
    tag = el.tag
    if isinstance(tag, str) and tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        if uri == WPML_NS:
            return f"wpml:{local}"
        return local
    return str(tag)


def _str_to_clark(tag: str) -> str:
    if tag.startswith("wpml:"):
        return f"{{{WPML_NS}}}{tag[5:]}"
    return f"{{{KML_NS}}}{tag}"


def _nsmap_to_attrs(nsmap: Optional[Dict[Optional[str], str]]) -> Dict[str, str]:
    if not nsmap:
        return {}
    out: Dict[str, str] = {}
    for pref, uri in nsmap.items():
        if pref is None:
            out["xmlns"] = uri
        else:
            out[f"xmlns:{pref}"] = uri
    return out


def _attrs_to_nsmap(attrs: Dict[str, str]) -> Dict[Optional[str], str]:
    nsmap: Dict[Optional[str], str] = {}
    for k, v in attrs.items():
        if k == "xmlns":
            nsmap[None] = v
        elif k.startswith("xmlns:"):
            nsmap[k.split(":", 1)[1]] = v
    if None not in nsmap:
        nsmap[None] = KML_NS
    if "wpml" not in nsmap:
        nsmap["wpml"] = WPML_NS
    return nsmap


def _attribs_from_element(el: etree._Element) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in el.attrib.items():
        if isinstance(k, str) and k.startswith("{"):
            uri, local = k[1:].split("}", 1)
            if uri == XMLNS_NS:
                if local == "xmlns":
                    out["xmlns"] = v
                else:
                    out[f"xmlns:{local}"] = v
            else:
                out[f"{{{uri}}}{local}"] = v
        else:
            out[k] = v
    return out


def _non_xmlns_attrs(attrs: Dict[str, str]) -> Dict[str, str]:
    return {k: v for k, v in attrs.items() if k != "xmlns" and not k.startswith("xmlns:")}


def _apply_non_xmlns_attribs(el: etree._Element, attrs: Dict[str, str]) -> None:
    for k, v in _non_xmlns_attrs(attrs).items():
        if k.startswith("{") and "}" in k:
            el.set(k, v)
        else:
            el.set(k, v)


def _element_children(el: etree._Element) -> List[etree._Element]:
    return [c for c in el if isinstance(c.tag, str)]


def element_to_node(el: etree._Element) -> DjiNode:
    """lxml 元素 → 节点 dict（tag / attrs / head? / body / tail）。"""
    tag = _tag_to_str(el)
    raw_attrs = _attribs_from_element(el)
    attrs: Dict[str, str] = dict(raw_attrs)
    if tag == "kml" and not raw_attrs:
        attrs = _nsmap_to_attrs(el.nsmap)

    kids = _element_children(el)
    tail = el.tail if el.tail is not None else ""

    if not kids:
        body = el.text if el.text is not None else ""
        node: DjiNode = {"tag": tag, "body": body, "tail": tail}
        if attrs:
            node["attrs"] = attrs
        return node

    body_list = [element_to_node(ch) for ch in kids]
    node = {"tag": tag, "body": body_list, "tail": tail}
    if attrs:
        node["attrs"] = attrs
    head = el.text
    if head is not None and head != "":
        node["head"] = head
    return node


def parse_kmz_member(zip_path: str, member: str = "wpmz/template.kml") -> DjiNode:
    """从 KMZ 内读取一条 KML/WPML 并解析为树（根 ``tag`` 为 ``kml``）。"""
    with zipfile.ZipFile(zip_path, "r") as zf:
        return parse_kml_bytes(zf.read(member))


def parse_kml_bytes(data: bytes) -> DjiNode:
    """解析字节；根节点 ``tag`` 须为 ``kml``。"""
    root = etree.fromstring(data)
    node = element_to_node(root)
    if node.get("tag") != "kml":
        raise ValueError("根节点须为 kml")
    base = _nsmap_to_attrs(root.nsmap)
    merged_attrs = {**base, **(node.get("attrs") or {})}
    out = copy.deepcopy(node)
    out["attrs"] = merged_attrs
    return out


def _serialize_element(node: DjiNode, parent: Optional[etree._Element] = None) -> etree._Element:
    tag = node["tag"]
    clark = _str_to_clark(tag)
    attrs = node.get("attrs") or {}

    if tag == "kml":
        el = etree.Element(clark, nsmap=_attrs_to_nsmap(attrs))
        _apply_non_xmlns_attribs(el, attrs)
    else:
        if parent is None:
            raise ValueError("非 kml 根须带 parent")
        el = etree.SubElement(parent, clark)
        _apply_non_xmlns_attribs(el, attrs)

    body = node.get("body")
    tail = node.get("tail", "")
    if tail is None:
        tail = ""

    if isinstance(body, list):
        if "head" in node:
            el.text = node["head"]
        else:
            el.text = None
        for ch in body:
            sub = _serialize_element(ch, el)
            t = ch.get("tail")
            sub.tail = t if t is not None else ""
        el.tail = tail
        return el

    if isinstance(body, str):
        el.text = body
    else:
        raise TypeError(f"body 须为 str 或 list，实际: {type(body)}")

    el.tail = tail
    return el


def serialize_tree(node: DjiNode, xml_declaration: bool = True, encoding: str = "utf-8") -> bytes:
    """树 → UTF-8 XML。"""
    if node.get("tag") != "kml":
        raise ValueError("根节点须为 kml")
    root = _serialize_element(node, None)
    return etree.tostring(
        root,
        encoding=encoding,
        xml_declaration=xml_declaration,
        pretty_print=False,
    )


def trees_semantic_equal(a: DjiNode, b: DjiNode) -> bool:
    """深度相等（``attrs`` 键值对顺序无关；``head``/``tail`` 缺省按空串）。"""
    if a.get("tag") != b.get("tag"):
        return False
    if (a.get("head") or "") != (b.get("head") or ""):
        return False
    if (a.get("tail") or "") != (b.get("tail") or ""):
        return False
    da = a.get("attrs") or {}
    db = b.get("attrs") or {}
    if sorted(da.items()) != sorted(db.items()):
        return False
    ba, bb = a.get("body"), b.get("body")
    if type(ba) != type(bb):
        return False
    if isinstance(ba, str):
        return ba == bb
    if len(ba) != len(bb):
        return False
    for x, y in zip(ba, bb):
        if not trees_semantic_equal(x, y):
            return False
    return True


# --- KML 形嵌套 dict（与 template.kml 缩进层级一致；键 = 标签名） ---

NESTED_ATTRIB_PREFIX = "@"


def node_to_kml_like(node: DjiNode) -> Dict[str, Any]:
    """``DjiNode`` → 嵌套 dict：``{"kml": {"@xmlns": "...", "Document": {...}}}``。

    * 根仅允许 ``tag`` 为 ``kml``。
    * 属性键为 ``@`` + 原 ``attrs`` 键（如 ``@xmlns``、``@xmlns:wpml``）。
    * 同名连续兄弟在 JSON 中合并为 **list**。
    """
    if node.get("tag") != "kml":
        raise ValueError("node_to_kml_like 仅接受根 tag 为 kml 的 DjiNode")
    inner: Dict[str, Any] = {}
    for ak, av in (node.get("attrs") or {}).items():
        inner[f"{NESTED_ATTRIB_PREFIX}{ak}"] = av
    body = node.get("body")
    if not isinstance(body, list):
        raise ValueError("根 kml 的 body 须为子节点列表")
    inner.update(_siblings_to_nested_map(body))
    return {"kml": inner}


def _node_to_nested_value(n: DjiNode) -> Any:
    b = n.get("body")
    if isinstance(b, str):
        return b
    if isinstance(b, list):
        d = _siblings_to_nested_map(b)
        for ak, av in (n.get("attrs") or {}).items():
            d[f"{NESTED_ATTRIB_PREFIX}{ak}"] = av
        return d
    raise TypeError(f"非法 body 类型: {type(b)}")


def _siblings_to_nested_map(children: List[DjiNode]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ch in children:
        t = ch["tag"]
        v = _node_to_nested_value(ch)
        if t not in out:
            out[t] = v
        else:
            prev = out[t]
            if isinstance(prev, list):
                prev.append(v)
            else:
                out[t] = [prev, v]
    return out


def kml_like_to_node(obj: Dict[str, Any]) -> DjiNode:
    """嵌套 dict → ``DjiNode``（``head``/``tail`` 置空，仅保结构与叶文本）。"""
    if not isinstance(obj, dict) or "kml" not in obj:
        raise ValueError("顶层须为 {\"kml\": {...}}")
    inner = obj["kml"]
    if not isinstance(inner, dict):
        raise TypeError("kml 的值须为 object")
    attrs: Dict[str, str] = {}
    child_items: List[tuple] = []
    for k, v in inner.items():
        if k.startswith(NESTED_ATTRIB_PREFIX):
            attrs[k[len(NESTED_ATTRIB_PREFIX) :]] = str(v)
        else:
            child_items.append((k, v))
    body: List[DjiNode] = []
    for tag, val in child_items:
        body.extend(_nested_expand(tag, val))
    return {"tag": "kml", "attrs": attrs, "body": body, "tail": ""}


def _nested_expand(tag: str, val: Any) -> List[DjiNode]:
    if isinstance(val, list):
        return [_nested_one(tag, x) for x in val]
    return [_nested_one(tag, val)]


def _nested_one(tag: str, val: Any) -> DjiNode:
    if isinstance(val, str):
        return {"tag": tag, "body": val, "tail": ""}
    if isinstance(val, dict):
        kids: List[DjiNode] = []
        for ck, cv in val.items():
            if ck.startswith(NESTED_ATTRIB_PREFIX):
                continue
            kids.extend(_nested_expand(ck, cv))
        n: DjiNode = {"tag": tag, "body": kids, "tail": ""}
        a: Dict[str, str] = {}
        for ck, cv in val.items():
            if ck.startswith(NESTED_ATTRIB_PREFIX):
                a[ck[len(NESTED_ATTRIB_PREFIX) :]] = str(cv)
        if a:
            n["attrs"] = a
        return n
    raise TypeError(f"不支持的嵌套值类型 {tag!r}: {type(val)}")


def parse_kml_bytes_kml_like(data: bytes) -> Dict[str, Any]:
    """解析 KML/WPML 字节 → KML 形嵌套 dict。"""
    return node_to_kml_like(parse_kml_bytes(data))


def parse_kmz_member_kml_like(zip_path: str, member: str = "wpmz/template.kml") -> Dict[str, Any]:
    """从 KMZ 读取成员 → KML 形嵌套 dict。"""
    with zipfile.ZipFile(zip_path, "r") as zf:
        return parse_kml_bytes_kml_like(zf.read(member))


def serialize_kml_like(
    obj: Dict[str, Any], xml_declaration: bool = True, encoding: str = "utf-8"
) -> bytes:
    """KML 形嵌套 dict → UTF-8 XML 字节串。"""
    return serialize_tree(kml_like_to_node(obj), xml_declaration=xml_declaration, encoding=encoding)


def collect_coordinates_nodes(node: DjiNode, out: Optional[List[str]] = None) -> List[str]:
    """按文档顺序收集 ``coordinates`` 叶 ``body`` 字符串。"""
    if out is None:
        out = []
    if node.get("tag") == "coordinates" and isinstance(node.get("body"), str):
        out.append(node["body"])
    body = node.get("body")
    if isinstance(body, list):
        for ch in body:
            collect_coordinates_nodes(ch, out)
    return out
