# MIT License
#
# Copyright (c) 2018 dr-BEat
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
from markdown import Markdown
from markdown.extensions.extra import ExtraExtension
from markdown.preprocessors import Preprocessor
from errbot.rendering.ansiext import AnsiExtension, enable_format, IMTEXT_CHRS

MARKDOWN_LINK_REGEX = re.compile(r'(?<!!)\[(?P<text>[^\]]+?)\]\((?P<uri>[a-zA-Z0-9]+?:\S+?)\)')


def hangoutschat_markdown_converter(compact_output=False):
    """
    This is a Markdown converter for use with HangoutsChat.
    """
    enable_format('imtext', IMTEXT_CHRS, borders=not compact_output)
    md = Markdown(output_format='imtext', extensions=[ExtraExtension(), AnsiExtension()])
    md.preprocessors['LinkPreProcessor'] = LinkPreProcessor(md)
    md.stripTopLevelTags = False
    return md


class LinkPreProcessor(Preprocessor):
    """
    This preprocessor converts markdown URL notation into Hangouts Chat URL
    notation as described at
    https://developers.google.com/hangouts/chat/reference/message-formats/basic,
    section "Linking to URLs".
    """
    def run(self, lines):
        for i, line in enumerate(lines):
            lines[i] = MARKDOWN_LINK_REGEX.sub(r'&lt;\2|\1&gt;', line)
        return lines
