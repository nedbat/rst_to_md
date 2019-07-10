from docutils import nodes, languages


class Context:
    def __init__(self):
        self.head = []
        self.body = []
        self.foot = []

    def put_head(self, text):
        self.head.append(text)

    def put_body(self, text):
        self.body.append(text)

    def put_foot(self, text):
        self.foot.append(text)

    def finalize(self):
        pass

    def __add__(self, other):
        self.head += other.head
        self.body += other.body
        self.foot += other.foot
        return self

    def astext(self):
        return ''.join(self.head + self.body + self.foot)


class Translator(nodes.NodeVisitor):

    def __init__(self, document):
        nodes.NodeVisitor.__init__(self, document)
        self.settings = settings = document.settings
        lcode = settings.language_code
        self.language = languages.get_language(lcode, document.reporter)

        self._context = [Context()]

        self.section_level = 0

        # TODO docinfo items can go in a footer HTML element (store in
        # self.foot).

        self._docinfo = {
            'title': '',
            'subtitle': '',
            'author': [],
            'date': '',
            'copyright': '',
            'version': '',
            }

        # Customise Markdown syntax here. Still need to add literal, term,
        # indent, problematic etc...
        self.defs = {
            'emphasis': ('*', '*'),   # Could also use ('_', '_')
            'problematic': ('\n\n', '\n\n'),
            'strong': ('**', '**'),  # Could also use ('__', '__')
            'subscript': ('<sub>', '</sub>'),
            'superscript': ('<sup>', '</sup>'),
            'literal': ('`', '`'),
            'math': ('$', '$'),
        }

    # Utility methods

    @property
    def output(self):
        return self._context[-1]

    def push_context(self, ctx):
        self._context.append(ctx)

    def pop_context(self):
        head = self._context[-1]
        head.finalize()
        self._context = self._context[:-1]
        self._context[-1] += head

    def astext(self):
        """Return the final formatted document as a string."""
        return self.output.astext()

    # TODO: Why are we doing this?
    def deunicode(self, text):
        text = text.replace(u'\xa0', u' ')  # non-breaking space
        text = text.replace(u'\u2020', '\\(dg')  # dagger
        return text

    def ensure_eol(self):
        """Ensure the last line in body is terminated by new line."""
        if self.body and self.body[-1][-1] != '\n':
            self.output.put_body('\n')

    # Node visitor methods

    # TODO: Can we let the user specify the default language to use here?
    def visit_literal_block(self, node):
        language = 'python'
        # AFAICT language is just another class name.
        # Can there be additional classes than the language name?
        for class_name in node.attributes['classes']:
            if class_name not in ('code', 'code-block'):
                language = class_name
                break
        class LiteralContext(Context):
            def __init__(self, language, *args, **kwargs):
                # passing language in constructor avoids scoping difficulties
                self.language = language
                Context.__init__(self, *args, **kwargs)     # py2 compatibility

            def finalize(self):
                language = self.language
                if self.body and self.body[0].startswith('>>>') and language=='python':
                    language = 'pycon'
                self.body = ['```{}\n'.format(language)] + self.body + ['\n```\n\n']

        self.push_context(LiteralContext(language))

    def depart_literal_block(self, node):
        self.pop_context()

    def visit_literal(self, node):
        self.output.put_body(self.defs['literal'][0])

    def depart_literal(self, node):
        self.output.put_body(self.defs['literal'][1])

    def visit_inline(self, node):
        # We need to silently handle inlines because sometimes (Can't work out when)
        # spurious inlines are generated in code blocks
        pass

    def depart_inline(self, node):
        pass

    def visit_block_quote(self, node):
        class QuoteContext(Context):
            def finalize(self):
                quoted = ['> {}'.format(line) for line in self.body[:1]] + self.body[1:]
                quoted = [line.replace('\n', '\n> ') for line in quoted[:-1]] + quoted[-1:]
                self.body = quoted
        self.push_context(QuoteContext())

    def depart_block_quote(self, node):
        self.pop_context()

    def visit_Text(self, node):
        self.output.put_body(node.astext())

    def depart_Text(self, node):
        pass

    def visit_comment(self, node):
        # self.body.append('<!-- ' + node.astext() + ' -->\n')
        raise nodes.SkipNode

    def visit_docinfo_item(self, node, name):
        if name == 'author':
            self._docinfo[name].append(node.astext())
        else:
            self._docinfo[name] = node.astext()
        raise nodes.SkipNode

    def visit_document(self, node):
        self.document = node

    def depart_document(self, node):
        pass

    def visit_emphasis(self, node):
        self.output.put_body(self.defs['emphasis'][0])

    def depart_emphasis(self, node):
        self.output.put_body(self.defs['emphasis'][1])

    def visit_paragraph(self, node):
        pass
        # self.ensure_eol()
        # self.output.put_body('\n')

    def depart_paragraph(self, node):
        self.output.put_body('\n\n')

    def visit_problematic(self, node):
        self.output.put_body(self.defs['problematic'][0])

    def depart_problematic(self, node):
        self.output.put_body(self.defs['problematic'][1])

    def visit_section(self, node):
        self.section_level += 1

    def depart_section(self, node):
        self.section_level -= 1

    def visit_strong(self, node):
        self.output.put_body(self.defs['strong'][0])

    def depart_strong(self, node):
        self.output.put_body(self.defs['strong'][1])

    def visit_subscript(self, node):
        self.output.put_body(self.defs['subscript'][0])

    def depart_subscript(self, node):
        self.output.put_body(self.defs['subscript'][1])

    def visit_subtitle(self, node):
        if isinstance(node.parent, nodes.document):
            self.visit_docinfo_item(node, 'subtitle')
            raise nodes.SkipNode

    def visit_superscript(self, node):
        self.output.put_body(self.defs['superscript'][0])

    def depart_superscript(self, node):

        self.output.put_body(self.defs['superscript'][1])

    def visit_system_message(self, node):
        # TODO add report_level
        #if node['level'] < self.document.reporter['writer'].report_level:
        #    Level is too low to display:
        #    raise nodes.SkipNode
        attr = {}
        backref_text = ''
        if node.hasattr('id'):
            attr['name'] = node['id']
        if node.hasattr('line'):
            line = ', line %s' % node['line']
        else:
            line = ''
        self.output.put_body('"System Message: %s/%s (%s:%s)"\n'
            % (node['type'], node['level'], node['source'], line))

    def depart_system_message(self, node):
        pass

    def visit_title(self, node):
        if self.section_level == 0:
            self.output.put_head('# {0}\n'.format(node.astext()))
            self._docinfo['title'] = node.astext()
            raise nodes.SkipNode
        else:
            self.output.put_body('{0} {1}\n'.format((self.section_level+1)*'#',
                self.deunicode(node.astext())))
            raise nodes.SkipNode

    def depart_title(self, node):
        self.output.put_body('\n')

    def visit_transition(self, node):
        # Simply replace a transition by a horizontal rule.
        # Could use three or more '*', '_' or '-'.
        self.output.put_body('\n---\n\n')
        raise nodes.SkipNode

    def visit_bullet_list(self, node):
        # There's nothing to do here, but we need this handler to avoid
        # conversion warnings.
        pass

    def depart_bullet_list(self, node):
        pass

    def visit_enumerated_list(self, node):
        pass

    def depart_enumerated_list(self, node):
        pass

    def visit_list_item(self, node):
        def fix_crs(text):
            return text\
                .replace('\n', '\n  ')\
                .replace('\n  \n', '\n\n')  # remove trailing whitespace.

        # TODO: Perhaps trailing whitepace removal should be a global operation.

        class ListItemContext(Context):
            def finalize(self):
                front = ['- {}'.format(fix_crs(l)) for l in self.body[:1]]
                middle = [fix_crs(e) for e in self.body[1:-1]]
                back = self.body[-1:]
                self.body = front + middle + back

        self.push_context(ListItemContext())

    def depart_list_item(self, node):
        self.pop_context()

    def visit_reference(self, node):
        self.output.put_body('[')

    def depart_reference(self, node):
        self.output.put_body(']({})'.format(node.attributes['refuri']))

    def visit_target(self, node):
        # We don't do targets right now. Should we?
        pass

    def depart_target(self, node):
        pass

    def visit_math(self, node):
        self.output.put_body(self.defs['math'][0])

    def depart_math(self, node):
        self.output.put_body(self.defs['math'][1])

    def visit_math_block(self, node):
        class MathContext(Context):
            def finalize(self):
                self.body = ['$$\n'] + [line.strip() for line in self.body] + ['\n$$\n\n']

        self.push_context(MathContext())

    def depart_math_block(self, node):
        self.pop_context()

# The following code adds visit/depart methods for any reSturcturedText element
# which we have not explicitly implemented above.

# All reStructuredText elements:
rst_elements = ('abbreviation', 'acronym', 'address', 'admonition',
    'attention', 'attribution', 'author', 'authors',
    'block_quote', 'bullet_list',
    'caption', 'caution', 'citation', 'citation_reference', 'classifier',
    'colspec', 'comment', 'compound', 'contact', 'container',
    'copyright',
    'danger', 'date', 'decoration', 'definition', 'definition_list',
    'definition_list_item', 'description', 'docinfo', 'doctest_block',
    'document',
    'emphasis', 'entry', 'enumerated_list', 'error',
    'field', 'field_body', 'field_list', 'field_name', 'figure', 'footer',
    'footnote', 'footnote_reference',
    'generated',
    'header', 'hint',
    'image', 'important', 'inline',
    'label', 'legend', 'line', 'line_block', 'list_item', 'literal',
    'literal_block',
    'math', 'math_block',
    'note',
    'option', 'option_argument', 'option_group', 'option_list',
    'option_list_item', 'option_string', 'organization',
    'paragraph', 'pending', 'problematic',
    'raw', 'reference', 'revision', 'row', 'rubric',
    'section', 'sidebar', 'status', 'strong', 'subscript',
    'substitution_definition', 'substitution_reference', 'subtitle',
    'superscript', 'system_message',
    'table', 'target', 'tbody,' 'term', 'tgroup', 'thead', 'tip', 'title',
    'title_reference', 'topic', 'transition',
    'version',
    'warning',)

##TODO Eventually we should silently ignore unsupported reStructuredText
##     constructs and document somewhere that they are not supported.
##     In the meantime raise a warning *once* for each unsupported element.
_warned = set()

def visit_unsupported(self, node):
    node_type = node.__class__.__name__
    if node_type not in _warned:
        self.document.reporter.warning('The ' + node_type + \
            ' element is not supported.')
        _warned.add(node_type)
    raise nodes.SkipNode

for element in rst_elements:
    if not hasattr(Translator, 'visit_' + element):
        setattr(Translator, 'visit_' + element , visit_unsupported)
