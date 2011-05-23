# coding: utf8

#  WeasyPrint converts web documents (HTML, CSS, ...) to PDF.
#  Copyright (C) 2011  Simon Sapin
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


from attest import Tests, assert_hook
from lxml import html

from .. import boxes
from .. import css


suite = Tests()


def serialize(box_list):
    """
    Transform a box list into a structure easier to compare for testing.
    """
    types = {
        boxes.BlockLevelBox: 'block',
        boxes.InlineLevelBox: 'inline',
        boxes.TextBox: 'text',
        boxes.AnonymousBlockLevelBox: 'anon_block',
        boxes.LineBox: 'line',
    }
    return [
        (box.element.tag, types[box.__class__], (
            box.text if isinstance(box, boxes.TextBox)
            else serialize(box.children)))
        for box in box_list
    ]


def unwrap_html_body(box):
    """
    Test that the box tree starts with an <html> block and a <body> block
    and remove them to simplify further tests. These are always at the root
    of HTML documents.
    """
    assert isinstance(box, boxes.BlockLevelBox)
    assert box.element.tag == 'html'
    assert len(box.children) == 1

    box = box.children[0]
    assert isinstance(box, boxes.BlockLevelBox)
    assert box.element.tag == 'body'
    
    return box.children


def to_lists(box_tree):
    """Serialize and unwrap <html> and <body>."""
    return serialize(unwrap_html_body(box_tree))
    

def parse(html_content):
    """
    Parse some HTML, apply stylesheets, transform to boxes, serialize.
    """
    document = html.document_fromstring(html_content)
    css.annotate_document(document)
    return boxes.dom_to_box(document)


def prettify(tree, indent=0):
    """Special formatting for printing serialized box trees."""
    prefix = '    ' * indent
    tag, type_, content = tree
    if type_ == 'text':
        return prefix + repr(tree)
    else:
        return '%s(%r, %r, [%s%s])' % (
            prefix, tag, type_,
            ('\n' if content else ''),
            ',\n'.join(prettify(child, indent + 1) for child in content)
        )


@suite.test
def test_box_tree():
    assert to_lists(parse('<p>')) == [('p', 'block', [])]
    assert to_lists(parse('<p>Hello <em>World</em>!</p>')) == [
        ('p', 'block', [
            ('p', 'text', 'Hello '),
            ('em', 'inline', [
                ('em', 'text', 'World')]),
            ('p', 'text', '!')])]


@suite.test
def test_inline_in_block():
    source = '<div>Hello, <em>World</em>!\n<p>Lipsum.</p></div>'
    expected = [
        ('div', 'block', [
            ('div', 'anon_block', [
                ('div', 'line', [
                    ('div', 'text', 'Hello, '),
                    ('em', 'inline', [
                        ('em', 'text', 'World')]),
                    ('div', 'text', '!\n')])]),
            ('p', 'block', [
                ('p', 'line', [
                    ('p', 'text', 'Lipsum.')])])])]
    
    box = parse(source)
    boxes.inline_in_block(box)
    assert to_lists(box) == expected

    box = parse(source)
    # This should be idempotent: doing more than once does not change anything.
    boxes.inline_in_block(box)
    boxes.inline_in_block(box)
    assert to_lists(box) == expected


@suite.test
def test_block_in_inline():
    box = parse('''
        <style>
            span { display: block; }
        </style>
        <p>Lorem <em>ipsum <strong>dolor <span>sit</span>
            <span>amet,</span></strong><span>consectetur</span></em></p>''')
    boxes.inline_in_block(box)
    expected = [
        ('p', 'block', [
            ('p', 'line', [
                ('p', 'text', 'Lorem '),
                ('em', 'inline', [
                    ('em', 'text', 'ipsum '),
                    ('strong', 'inline', [
                        ('strong', 'text', 'dolor '),
                        ('span', 'block', [ # This block is "pulled up"
                            ('span', 'line', [
                                ('span', 'text', 'sit')])]),
                        ('strong', 'text', '\n            '),
                        ('span', 'block', [ # This block is "pulled up"
                            ('span', 'line', [
                                ('span', 'text', 'amet,')])])]),
                    ('span', 'block', [ # This block is "pulled up"
                        ('span', 'line', [
                            ('span', 'text', 'consectetur')])])])])])]
#    print prettify(to_lists(box)[0])
    assert to_lists(box) == expected

    boxes.block_in_inline(box)
    expected = [
        ('p', 'block', [
            ('p', 'anon_block', [
                ('p', 'line', [
                    ('p', 'text', 'Lorem '),
                    ('em', 'inline', [
                        ('em', 'text', 'ipsum '),
                        ('strong', 'inline', [
                            ('strong', 'text', 'dolor ')])])])]),
            ('span', 'block', [
                ('span', 'line', [
                    ('span', 'text', 'sit')])]),
            # TODO: this should disapear
            ('p', 'anon_block', [
                ('p', 'line', [
                    ('em', 'inline', [
                        ('strong', 'inline', [
                            ('strong', 'text', '\n            ')])])])]),
            ('span', 'block', [
                ('span', 'line', [
                    ('span', 'text', 'amet,')])]),
                                    
            ('p', 'anon_block', [
                ('p', 'line', [
                    ('em', 'inline', [
                        ('strong', 'inline', [])])])]),
            ('span', 'block', [
                ('span', 'line', [
                    ('span', 'text', 'consectetur')])]),
            ('p', 'anon_block', [
                ('p', 'line', [
                    ('em', 'inline', [])])])])]
    
#    print prettify(to_lists(box)[0])
    assert to_lists(box) == expected


def descendant_boxes(box):
    """A flat generator for a box, its children and descendants."""
    yield box
    for child in box.children or []:
        for grand_child in descendant_boxes(child):
            yield grand_child


@suite.test
def test_styles():
    box = parse('''
        <style>
            span { display: block; }
            * { margin: 42px }
            html { color: blue }
        </style>
        <p>Lorem <em>ipsum <strong>dolor <span>sit</span>
            <span>amet,</span></strong><span>consectetur</span></em></p>''')
    boxes.inline_in_block(box)
    boxes.block_in_inline(box)
    
    for child in descendant_boxes(box):
        # All boxes inherit the color
        assert child.style.color == 'blue'
        # Only non-anonymous boxes have margins
        if isinstance(child, boxes.AnonymousBox):
            assert child.style.margin_top == 0
        else:
            assert child.style.margin_top == 42

