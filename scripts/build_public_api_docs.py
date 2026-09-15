import ast
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
modules = {}
for path in (root / 'ser_lib').rglob('*.py'):
    module = '.'.join(path.relative_to(root).with_suffix('').parts)
    if module.endswith('.__init__'):
        module = module[:-9]
    source = path.read_text(encoding='utf-8')
    modules[module] = (path, ast.parse(source), source)

def bindings(module):
    result = {}
    for node in modules[module][1].body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = node
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                result[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            result[node.target.id] = node
    return result

tables = {m: bindings(m) for m in modules}
def resolve(module, name, seen=()):
    if (module, name) in seen or module not in tables:
        raise ValueError((module, name))
    node = tables[module].get(name)
    if isinstance(node, tuple):
        return resolve(*node, seen=seen + ((module, name),))
    if node is None and module == 'ser_lib':
        mapping = ast.literal_eval(tables[module]['_LAZY_EXPORTS'].value)
        return resolve(*mapping[name])
    if node is None:
        raise ValueError((module, name))
    return module, name, node

exports = {}
for module, table in tables.items():
    if '__all__' in table:
        exports[module] = ast.literal_eval(table['__all__'].value)
exports.setdefault('ser_lib.cli.main', ['main'])

def esc(value):
    return str(value).replace('|', '&#124;').replace('\n', ' ')
def code(node):
    return ast.unparse(node)
def doc(node):
    return ast.get_docstring(node) or ''
def signature(node):
    return f'{node.name}({code(node.args)}) -> {code(node.returns) if node.returns else "未声明返回类型"}'

parts = []
def add(value=''):
    parts.append(value + '\n')
def function(node, heading=True):
    if heading:
        add(f'##### `{node.name}`\n')
    decorators = [code(d) for d in node.decorator_list]
    if 'property' in decorators:
        add('调用方式：只读属性。\n')
    elif 'classmethod' in decorators:
        add('调用方式：类方法，可直接通过类名调用。\n')
    elif 'staticmethod' in decorators:
        add('调用方式：静态方法。\n')
    add('```python\n' + signature(node) + '\n```\n')
    if doc(node):
        add(doc(node) + '\n')
    elif node.name == '__init__':
        add('作用：按上述参数构造实例；后续通过该实例的公开方法执行操作。\n')
    elif node.name == 'to_dict':
        add('作用：将对象当前字段转换为字典，供日志、JSON 输出或应用层集成。\n')
    # Preserve directly expressed result structures and error contracts without
    # claiming branch-dependent expressions are unconditional output schemas.
    returns = []
    errors = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
            expression = code(sub.value)
            if expression not in returns:
                returns.append(expression)
        if isinstance(sub, ast.Raise) and sub.exc:
            expression = code(sub.exc)
            if expression not in errors:
                errors.append(expression)
    if returns:
        add('返回字典的源码字段表达式（不同分支可能不同；变量表示运行时值）：\n')
        for expression in returns:
            add('```python\n' + expression + '\n```\n')
    if errors:
        add('实现中显式检查的错误条件（条件满足时抛出；不包括依赖层的全部异常）：\n')
        for expression in errors:
            add('- `' + expression.replace('`', "'") + '`')
        add()

unique = {}
aliases = {}
for module, names in exports.items():
    for name in names:
        impl, original, node = resolve(module, name)
        key = (impl, original)
        unique[key] = node
        aliases.setdefault(key, []).append(module + '.' + name)

add(f'本字典覆盖 **{len(exports)} 个声明公开导出的模块、{sum(map(len, exports.values()))} 个导出路径、{len(unique)} 个去重实现**（包括 CLI main）。\n')
add('### 9.1 全部导出路径索引\n')
for module in sorted(exports):
    add(f'#### `{module}`\n')
    for name in exports[module]:
        impl, original, _ = resolve(module, name)
        anchor = (impl + '.' + original).lower().replace('.', '-')
        add(f'- [`{name}`](#{anchor})')
    add()
add('### 9.2 定义、参数、返回值与约束\n')
for (module, name), node in sorted(unique.items()):
    anchor = (module + '.' + name).lower().replace('.', '-')
    add(f'<a id="{anchor}"></a>\n')
    add(f'#### `{module}.{name}`\n')
    add('公开导入：' + '、'.join('`' + a + '`' for a in aliases[(module, name)]) + '。\n')
    path = modules[module][0].relative_to(root).as_posix()
    add(f'源码：[{path}:{node.lineno}](../{path}#L{node.lineno})。\n')
    if isinstance(node, ast.ClassDef):
        if doc(node):
            add(doc(node) + '\n')
        if node.bases:
            add('基类：' + '、'.join('`' + code(b) + '`' for b in node.bases) + '。继承的字段/方法继续适用。\n')
        fields = [n for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and not n.target.id.startswith('_')]
        if fields:
            add('| 字段 | 类型 | 默认值 / 校验 / 描述 |\n|---|---|---|')
            for field in fields:
                add(f'| `{field.target.id}` | `{esc(code(field.annotation))}` | `{esc(code(field.value)) if field.value else "必填（无默认值）"}` |')
            add()
        post = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '__post_init__'), None)
        if post:
            errors = list(dict.fromkeys(code(n.exc) for n in ast.walk(post) if isinstance(n, ast.Raise) and n.exc))
            if errors:
                add('构造时的字段约束：\n')
                for error in errors:
                    add('- `' + error.replace('`', "'") + '`')
                add()
        for method in node.body:
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not method.name.startswith('_') or method.name in {'__init__', '__call__', '__getitem__', '__len__', '__iter__', '__enter__', '__exit__'}):
                function(method)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        function(node, heading=False)
    else:
        add('类型别名、常量或共享实例定义：\n')
        add('```python\n' + code(node) + '\n```\n')

target = root / 'docs/MAIN_PUBLIC_INTERFACES.md'
base = target.read_text(encoding='utf-8').split('<!-- GENERATED API DICTIONARY -->')[0]
target.write_text(base + '<!-- GENERATED API DICTIONARY -->\n\n' + ''.join(parts), encoding='utf-8')
# Coverage and local link validation are documentation-only checks.
text = target.read_text(encoding='utf-8')
for key in unique:
    assert f'<a id="{(".".join(key)).lower().replace(".", "-")}"></a>' in text
for dest in re.findall(r'\]\((\.\./[^)#]+)', text):
    assert (target.parent / dest).exists(), dest
print(f'Validated: {len(exports)} modules, {sum(map(len, exports.values()))} export paths, {len(unique)} implementations; {len(text.splitlines())} lines')
