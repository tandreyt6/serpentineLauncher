import ast
from io import StringIO
from pathlib import Path
import tokenize


def python_annotations(source):
    tree = ast.parse(source)
    documents = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node, clean=False) is not None:
            documents.append((node.body[0], len(node.body) == 1 and not isinstance(node, ast.Module)))
    comments = [token for token in tokenize.generate_tokens(StringIO(source).readline) if token.type == tokenize.COMMENT]
    return documents, comments


def strip_python(source):
    documents, comments = python_annotations(source)
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def position(line, column, byte_column=False):
        if byte_column:
            column = len(lines[line - 1].encode('utf-8')[:column].decode('utf-8'))
        return offsets[line - 1] + column

    spans = [(position(token.start[0], token.start[1]), position(token.end[0], token.end[1]), '') for token in comments]
    spans.extend((position(node.lineno, node.col_offset, True), position(node.end_lineno, node.end_col_offset, True), 'pass' if alone else '') for node, alone in documents)
    result = source
    for start, end, replacement in sorted(spans, reverse=True):
        blank = ''.join('\n' if character == '\n' else '\r' if character == '\r' else ' ' for character in result[start:end])
        result = result[:start] + replacement + blank[len(replacement):] + result[end:]
    result = '\n'.join(line.rstrip() for line in result.splitlines()) + ('\n' if source.endswith('\n') else '')
    ast.parse(result)
    return result


def script_comments(source):
    spans = []
    index = 0
    quote = ''
    regular_expression = False
    character_class = False
    while index < len(source):
        character = source[index]
        if regular_expression:
            if character == '\\':
                index += 2
                continue
            if character == '[':
                character_class = True
            elif character == ']':
                character_class = False
            elif character == '/' and not character_class:
                regular_expression = False
            index += 1
            continue
        if quote:
            if character == '\\':
                index += 2
                continue
            if character == quote:
                quote = ''
            index += 1
            continue
        if character in "\"'`":
            quote = character
            index += 1
            continue
        if source.startswith('//', index):
            end = source.find('\n', index)
            end = len(source) if end < 0 else end
        elif source.startswith('/*', index):
            end = source.find('*/', index + 2)
            if end < 0:
                raise ValueError('Unterminated block comment')
            end += 2
        else:
            if character == '/':
                preceding = source[:index].rstrip()
                if not preceding or preceding[-1] in '=(:,[!&|?;{' or preceding.endswith('return'):
                    regular_expression = True
            index += 1
            continue
        spans.append((index, end))
        index = end
    return spans


def strip_script(source):
    result = source
    for start, end in reversed(script_comments(source)):
        blank = ''.join('\n' if character == '\n' else ' ' for character in result[start:end])
        result = result[:start] + blank + result[end:]
    return '\n'.join(line.rstrip() for line in result.splitlines()) + ('\n' if source.endswith('\n') else '')


def clean_file(path):
    source = path.read_text(encoding='utf-8-sig')
    result = strip_python(source) if path.suffix == '.py' else strip_script(source)
    if result != source:
        path.write_text(result, encoding='utf-8')
        return True
    return False


def owned_sources(root):
    roots = ('Core', 'ui', 'theme_sources', 'ThemeWorkbench/prototypes', 'ThemeWorkbench/examples',
             'ThemeWorkbench/scenes', 'ThemeWorkbench/snapshot/ui')
    paths = set(root.glob('*.py'))
    for name in roots:
        paths.update(path for path in (root / name).rglob('*') if path.suffix in ('.py', '.qml', '.js') and '__pycache__' not in path.parts)
    return sorted(paths)
