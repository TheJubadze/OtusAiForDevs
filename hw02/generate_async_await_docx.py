from __future__ import annotations

import argparse
import datetime as _dt
import html
import os
import zipfile


def _hp(points: int) -> int:
    """Convert points to half-points for OOXML w:sz."""
    return points * 2


def _t(text: str) -> str:
    return html.escape(text, quote=False)


def _p(
    text: str,
    *,
    bold: bool = False,
    size_pt: int | None = None,
    center: bool = False,
    space_after: int | None = 160,
    space_before: int | None = None,
    monospace: bool = False,
    shading_fill: str | None = None,
) -> str:
    ppr_parts: list[str] = []
    if center:
        ppr_parts.append('<w:jc w:val="center"/>')
    if space_after is not None or space_before is not None:
        attrs: list[str] = []
        if space_before is not None:
            attrs.append(f'w:before="{space_before}"')
        if space_after is not None:
            attrs.append(f'w:after="{space_after}"')
        ppr_parts.append(f"<w:spacing {' '.join(attrs)}/>")
    ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>" if ppr_parts else ""

    rpr_parts: list[str] = []
    if bold:
        rpr_parts.append("<w:b/>")
    if size_pt is not None:
        sz = _hp(size_pt)
        rpr_parts.append(f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>')
    if monospace:
        rpr_parts.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>')
    if shading_fill is not None:
        rpr_parts.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{_t(shading_fill)}"/>')
    rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""

    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{_t(text)}</w:t></w:r></w:p>'


def _blank(space_after: int = 80) -> str:
    return _p("", space_after=space_after)


def _code_block(lines: list[str]) -> str:
    parts: list[str] = []
    parts.append(_p("", space_after=80))
    for line in lines:
        parts.append(
            _p(
                line,
                monospace=True,
                size_pt=10,
                space_after=0,
                shading_fill="F2F2F2",
            )
        )
    parts.append(_p("", space_after=120))
    return "".join(parts)

def _table(rows: list[list[str]], *, header: bool = False) -> str:
    # Minimal table implementation (no numbering/styles part needed).
    # Widths: 30% / 70% of usable page width (A4 with 1" margins ~ 9360 twips).
    col1 = 2800
    col2 = 6560

    def tc(text: str, *, is_header: bool) -> str:
        run = f"<w:r><w:rPr>{'<w:b/>' if is_header else ''}</w:rPr><w:t xml:space=\"preserve\">{_t(text)}</w:t></w:r>"
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{col1 if is_header is False else col1}" w:type="dxa"/></w:tcPr>'
            f"<w:p><w:pPr><w:spacing w:before=\"80\" w:after=\"80\"/></w:pPr>{run}</w:p></w:tc>"
        )

    def tcw(text: str, width: int, *, is_header: bool) -> str:
        run = f"<w:r><w:rPr>{'<w:b/>' if is_header else ''}</w:rPr><w:t xml:space=\"preserve\">{_t(text)}</w:t></w:r>"
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
            f"<w:p><w:pPr><w:spacing w:before=\"80\" w:after=\"80\"/></w:pPr>{run}</w:p></w:tc>"
        )

    tbl_pr = """
<w:tblPr>
  <w:tblW w:w="0" w:type="auto"/>
  <w:tblBorders>
    <w:top w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
    <w:left w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
    <w:bottom w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
    <w:right w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
    <w:insideH w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
    <w:insideV w:val="single" w:sz="6" w:space="0" w:color="D0D0D0"/>
  </w:tblBorders>
</w:tblPr>
"""
    tbl_grid = f'<w:tblGrid><w:gridCol w:w="{col1}"/><w:gridCol w:w="{col2}"/></w:tblGrid>'
    trs: list[str] = []
    for row_index, row in enumerate(rows):
        is_header = header and row_index == 0
        left = row[0] if len(row) > 0 else ""
        right = row[1] if len(row) > 1 else ""
        trs.append(
            "<w:tr>"
            + tcw(left, col1, is_header=is_header)
            + tcw(right, col2, is_header=is_header)
            + "</w:tr>"
        )
    return "<w:tbl>" + tbl_pr + tbl_grid + "".join(trs) + "</w:tbl>"


def _section(title: str, paragraphs: list[str]) -> str:
    parts: list[str] = []
    parts.append(_p(title, bold=True, size_pt=16, space_before=240, space_after=120))
    for par in paragraphs:
        parts.append(_p(par, size_pt=11, space_after=120))
    return "".join(parts)


def _doc_xml(body_inner: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {body_inner}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                Target="word/document.xml"/>
  <Relationship Id="rId2"
                Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
                Target="docProps/core.xml"/>
  <Relationship Id="rId3"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
                Target="docProps/app.xml"/>
</Relationships>
"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
                Target="styles.xml"/>
</Relationships>
"""


def _styles_xml() -> str:
    # Minimal styles to keep Word happy; we still set formatting directly in runs.
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
</w:styles>
"""


def _core_props_xml(title: str) -> str:
    now = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
  xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{_t(title)}</dc:title>
  <dc:creator>Codex CLI</dc:creator>
  <cp:lastModifiedBy>Codex CLI</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
            xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex CLI</Application>
</Properties>
"""


def _write_docx(output_path: str, *, title: str, body_inner: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml())
        zf.writestr("_rels/.rels", _rels_xml())
        zf.writestr("word/document.xml", _doc_xml(body_inner))
        zf.writestr("word/_rels/document.xml.rels", _document_rels_xml())
        zf.writestr("word/styles.xml", _styles_xml())
        zf.writestr("docProps/core.xml", _core_props_xml(title))
        zf.writestr("docProps/app.xml", _app_props_xml())


def build_overview_docx(output_path: str) -> None:
    title = "Async/await в dotnet/runtime: CoreLib"
    subtitle = "Разбор реализации на уровне System.Private.CoreLib"

    body: list[str] = []
    body.append(_p(title, bold=True, size_pt=26, center=True, space_after=120))
    body.append(_p(subtitle, size_pt=12, center=True, space_after=240))

    body.append(
        _section(
            "1. Идея: контракт компилятора и рантайма",
            [
                "В C# async/await — это синтаксический сахар. Компилятор превращает async-метод в state machine, а рантайм предоставляет типы builder/awaiter и механизм постановки продолжений (continuations).",
                "В CoreLib это видно по связке IAsyncStateMachine + AsyncTaskMethodBuilder<TResult> + TaskAwaiter + Task.",
            ],
        )
    )

    body.append(
        _section(
            "2. State machine: IAsyncStateMachine",
            [
                "Компилятор генерирует структуру/класс, реализующий IAsyncStateMachine.MoveNext(). В MoveNext() хранится switch по состоянию и логика «до await / после await».",
                "Контракт минимален: MoveNext() и SetStateMachine(...).",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/IAsyncStateMachine.cs:21",
            ],
        )
    )

    body.append(
        _section(
            "3. Запуск async-метода: AsyncMethodBuilderCore.Start",
            [
                "Builder.Start вызывает AsyncMethodBuilderCore.Start(ref stateMachine).",
                "Start вызывает первый stateMachine.MoveNext(), но перед этим сохраняет текущие ExecutionContext и SynchronizationContext, а затем восстанавливает их в finally.",
                "Это предотвращает «утечки» изменений контекста наружу до первого await.",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncMethodBuilderCore.cs:21",
            ],
        )
    )

    body.append(
        _section(
            "4. await: как подвешивание превращается в continuation",
            [
                "Паттерн await: awaiter = expr.GetAwaiter(); if (!awaiter.IsCompleted) { builder.AwaitUnsafeOnCompleted(ref awaiter, ref this); return; } awaiter.GetResult();",
                "Builder подписывает «продолжить MoveNext()» на завершение awaiter’а.",
                "Код развёртки (пример) есть в комментарии: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/YieldAwaitable.cs:46",
            ],
        )
    )

    body.append(
        _section(
            "5. AsyncTaskMethodBuilder<TResult>: box как Task + state machine",
            [
                "AsyncTaskMethodBuilder<TResult> хранит поле m_task (Task<TResult>?), инициализируемое лениво.",
                "На первом «реальном» await рантайм создаёт AsyncStateMachineBox<TStateMachine> и кладёт его в m_task.",
                "AsyncStateMachineBox<TStateMachine> наследуется от Task<TResult> и дополнительно хранит StateMachine, MoveNextAction и ExecutionContext.",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:153 (GetStateMachineBox), :279 (AsyncStateMachineBox), :329 (MoveNextAction), :338 (Context)",
            ],
        )
    )

    body.append(
        _section(
            "6. Быстрый путь для TaskAwaiter: UnsafeOnCompletedInternal",
            [
                "Если awaiter — это TaskAwaiter/ConfiguredTaskAwaiter, builder идёт по fast-path: TaskAwaiter.UnsafeOnCompletedInternal(task, box, continueOnCapturedContext).",
                "Это позволяет передать stateMachineBox напрямую в Task как continuation (без выделения Action/closure), когда трассировка/отладка выключены.",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:107 и src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/TaskAwaiter.cs:193",
            ],
        )
    )

    body.append(
        _section(
            "7. Где решается «в какой контекст возвращаться»",
            [
                "Task.SetContinuationForAwait выбирает, куда планировать continuation: SynchronizationContext (если не дефолтный), иначе TaskScheduler (если не Default), иначе ThreadPool.",
                "Параметр continueOnCapturedContext управляется обычным await vs ConfigureAwait(false).",
                "Код: src/libraries/System.Private.CoreLib/src/System/Threading/Tasks/Task.cs:2485",
                "Unsafe-путь без событий: src/libraries/System.Private.CoreLib/src/System/Threading/Tasks/Task.cs:2557",
            ],
        )
    )

    body.append(
        _section(
            "8. ExecutionContext и AsyncLocal: захват и восстановление",
            [
                "Для корректного переноса AsyncLocal между точками подвеса builder захватывает ExecutionContext через CaptureForSuspension(Thread.CurrentThread) и хранит его в box.Context.",
                "При вызове box.MoveNext() выполнение происходит под сохранённым ExecutionContext (или напрямую, если flow suppressed).",
                "Код: src/libraries/System.Private.CoreLib/src/System/Threading/ExecutionContext.cs:86 и src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:153",
            ],
        )
    )

    body.append(
        _section(
            "9. ValueTask / Yield: оптимизация через IStateMachineBoxAwareAwaiter",
            [
                "Некоторые awaiter’ы умеют принимать IAsyncStateMachineBox напрямую (IStateMachineBoxAwareAwaiter). Это позволяет планировать continuation без промежуточного Action даже для ValueTask/IValueTaskSource.",
                "Пример: YieldAwaitable.YieldAwaiter реализует IStateMachineBoxAwareAwaiter и сам ставит box в нужный контекст/планировщик.",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/ValueTaskAwaiter.cs:189 и src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/YieldAwaitable.cs:115",
            ],
        )
    )

    body.append(
        _section(
            "10. Исключения и отмена: GetResult/ValidateEnd",
            [
                "await завершает операцию вызовом awaiter.GetResult(). Для TaskAwaiter это ValidateEnd(task), который при необходимости выбрасывает исключение/TaskCanceledException.",
                "Код: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/TaskAwaiter.cs:66 и :79",
            ],
        )
    )

    body.append(_p("Псевдокод одного await (как мыслит компилятор)", bold=True, size_pt=16, space_before=240, space_after=120))
    body.append(
        _code_block(
            [
                "var awaiter = task.GetAwaiter();",
                "if (!awaiter.IsCompleted)",
                "{",
                "    state = N;",
                "    builder.AwaitUnsafeOnCompleted(ref awaiter, ref this);",
                "    return;",
                "}",
                "LabelN:",
                "awaiter.GetResult(); // может бросить исключение/отмену",
                "// ... продолжение MoveNext()",
            ]
        )
    )

    body.append(_blank())
    body_xml = "".join(body)

    _write_docx(output_path, title=title, body_inner=body_xml)


def build_state_machine_docx(output_path: str) -> None:
    title = "Async state machine в dotnet/runtime: подробный разбор"
    subtitle = "Как компилятор и CoreLib вместе реализуют возобновление (resume) и хранение состояния"

    body: list[str] = []
    body.append(_p(title, bold=True, size_pt=24, center=True, space_after=100))
    body.append(_p(subtitle, size_pt=12, center=True, space_after=240))

    body.append(
        _section(
            "0. Опорные файлы (CoreLib)",
            [
                "IAsyncStateMachine: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/IAsyncStateMachine.cs",
                "AsyncMethodBuilderCore.Start: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncMethodBuilderCore.cs:21",
                "AsyncTaskMethodBuilder<TResult> и AsyncStateMachineBox: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:153 / :279",
                "IAsyncStateMachineBox: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/IAsyncStateMachineBox.cs:9",
                "TaskAwaiter: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/TaskAwaiter.cs:174 / :193",
                "Task continuation plumbing: src/libraries/System.Private.CoreLib/src/System/Threading/Tasks/Task.cs:2485 / :2557",
                "ExecutionContext capture: src/libraries/System.Private.CoreLib/src/System/Threading/ExecutionContext.cs:86",
            ],
        )
    )

    body.append(
        _section(
            "1. Что такое «async state machine» на практике",
            [
                "Компилятор превращает тело async-метода в метод MoveNext() на сгенерированном типе, который хранит все «поднятые» (lifted) локальные переменные и текущий номер состояния.",
                "Каждый await — это потенциальная точка приостановки (suspension point): до неё выполняется код синхронно, после неё продолжение будет выполнено как continuation.",
                "Рантайм не «исполняет async сам»: он предоставляет builder и awaiter’ы, чтобы компилятор мог выразить suspend/resume через единый протокол.",
            ],
        )
    )

    body.append(_p("Классическая форма сгенерированного типа (псевдокод)", bold=True, size_pt=16, space_before=240, space_after=120))
    body.append(
        _code_block(
            [
                "struct <Foo>d__N : IAsyncStateMachine",
                "{",
                "    public int <>1__state;                       // текущее состояние",
                "    public AsyncTaskMethodBuilder<TResult> <>t__builder; // builder",
                "    // lifted locals / параметры / awaiter-поля:",
                "    private TaskAwaiter <>u__1;                   // хранение awaiter между suspend/resume",
                "",
                "    public void MoveNext()",
                "    {",
                "        int state = <>1__state;",
                "        try",
                "        {",
                "            if (state == 0) goto AfterAwait1;",
                "            // ... код до первого await ...",
                "            var awaiter = task.GetAwaiter();",
                "            if (!awaiter.IsCompleted)",
                "            {",
                "                <>1__state = 0;",
                "                <>u__1 = awaiter;",
                "                <>t__builder.AwaitUnsafeOnCompleted(ref <>u__1, ref this);",
                "                return;",
                "            }",
                "AfterAwait1:",
                "            <>u__1.GetResult();",
                "            // ... код после await ...",
                "        }",
                "        catch (Exception e)",
                "        {",
                "            <>1__state = -2;",
                "            <>t__builder.SetException(e);",
                "            return;",
                "        }",
                "        <>1__state = -2;",
                "        <>t__builder.SetResult(result);",
                "    }",
                "",
                "    public void SetStateMachine(IAsyncStateMachine sm) => <>t__builder.SetStateMachine(sm);",
                "}",
            ]
        )
    )

    body.append(
        _section(
            "2. Роли полей: state, builder, awaiter-поля",
            [
                "State (обычно int): позволяет MoveNext() «перепрыгнуть» к нужной точке после возобновления.",
                "Awaiter-поля: нужны, чтобы сохранить awaiter между return на suspension point и повторным входом в MoveNext().",
                "Builder: связывает state machine с Task/ValueTask и предоставляет операции подписки на await и завершения (SetResult/SetException).",
            ],
        )
    )

    body.append(
        _p("Справочная таблица: «что хранится где»", bold=True, size_pt=16, space_before=240, space_after=120)
    )
    body.append(
        _table(
            [
                ["Элемент", "Назначение"],
                ["`<>1__state`", "Номер состояния для переходов внутри MoveNext() (до/после await)."],
                ["`<>t__builder`", "Строит Task/ValueTask и умеет подписывать continuation на awaiter."],
                ["Awaiter-поля (например `<>u__1`)", "Хранят awaiter между suspend/resume."],
                ["`AsyncStateMachineBox<TStateMachine>`", "Heap-объект: одновременно `Task<TResult>` + ссылочная «коробка» для state machine + `ExecutionContext`."],
            ],
            header=True,
        )
    )
    body.append(_blank(120))

    body.append(
        _section(
            "3. Первый вход: AsyncMethodBuilderCore.Start",
            [
                "Компилятор вызывает builder.Start(ref stateMachine), а тот — AsyncMethodBuilderCore.Start(ref stateMachine).",
                "Start вызывает stateMachine.MoveNext(), но делает важный трюк: сохраняет ExecutionContext и SynchronizationContext до вызова и восстанавливает их после (finally).",
                "Это защищает внешнего вызывающего от изменений контекста, сделанных внутри первой синхронной части async-метода.",
            ],
        )
    )

    body.append(
        _section(
            "4. Suspension point: что делает builder.AwaitUnsafeOnCompleted",
            [
                "На точке await (когда awaiter.IsCompleted == false) MoveNext() сохраняет state и awaiter-поле, вызывает builder.AwaitUnsafeOnCompleted(...) и возвращает управление вызывающему.",
                "В CoreLib AwaitUnsafeOnCompleted получает/создаёт «коробку» state machine: GetStateMachineBox(...).",
                "Дальше, для TaskAwaiter, включается fast-path: TaskAwaiter.UnsafeOnCompletedInternal(task, box, ...).",
            ],
        )
    )

    body.append(_p("Ключевой объект: IAsyncStateMachineBox", bold=True, size_pt=16, space_before=240, space_after=120))
    body.append(
        _code_block(
            [
                "internal interface IAsyncStateMachineBox",
                "{",
                "    void MoveNext();",
                "    Action MoveNextAction { get; }",
                "    IAsyncStateMachine GetStateMachineObject(); // только для debug",
                "    void ClearStateUponCompletion();",
                "}",
                "// src/.../IAsyncStateMachineBox.cs:9",
            ]
        )
    )

    body.append(
        _section(
            "5. Как устроена коробка: AsyncStateMachineBox<TStateMachine>",
            [
                "AsyncStateMachineBox<TStateMachine> — это Task<TResult>, который дополнительно содержит state machine и контекст выполнения.",
                "MoveNextAction кэширует делегат, который приводит к вызову box.MoveNext(). Это «ручка», которую регистрируют как continuation.",
                "ExecutionContext хранится в базовом Task.m_stateObject (с включенным HiddenState), чтобы он не «утёк» через Task.AsyncState.",
            ],
        )
    )

    body.append(_p("Resume path в CoreLib (высокий уровень)", bold=True, size_pt=16, space_before=240, space_after=120))
    body.append(
        _code_block(
            [
                "await → builder.GetStateMachineBox()",
                "     → (TaskAwaiter) TaskAwaiter.UnsafeOnCompletedInternal(awaitedTask, box, ...)",
                "         → awaitedTask.UnsafeSetContinuationForAwait(box, ...)",
                "",
                "awaitedTask completes → schedules continuation",
                "     → box.MoveNext()",
                "         → ExecutionContext.RunInternal(box.Context, callback)",
                "             → stateMachine.MoveNext() // возвращение в сгенерированный MoveNext",
            ]
        )
    )

    body.append(
        _section(
            "6. Планирование continuation: SynchronizationContext / TaskScheduler / ThreadPool",
            [
                "Решение «куда продолжать» находится в Task.SetContinuationForAwait(...): при continueOnCapturedContext=true сначала пробуют non-default SynchronizationContext, затем non-default TaskScheduler, иначе ThreadPool.",
                "В unsafe fast-path (без событий/отладочных хуков) Task может принять IAsyncStateMachineBox напрямую как continuation.",
            ],
        )
    )

    body.append(
        _section(
            "7. ExecutionContext и AsyncLocal: почему захват делается на каждом await",
            [
                "Перед тем как зарегистрировать continuation, builder захватывает ExecutionContext через CaptureForSuspension(Thread.CurrentThread).",
                "Это позволяет корректно восстановить AsyncLocal на момент возобновления, даже если продолжение выполнится на другом потоке.",
                "Внутри box.MoveNext() выполнение происходит либо напрямую (flow suppressed), либо внутри ExecutionContext.RunInternal / RunFromThreadPoolDispatchLoop.",
            ],
        )
    )

    body.append(
        _section(
            "8. Завершение async-метода: SetResult / SetException и очистка состояния",
            [
                "Когда MoveNext() доходит до конца без исключений, компилятор вызывает builder.SetResult(...). При исключении — builder.SetException(e).",
                "Если state machine использовала box, то после завершения box очищает StateMachine и Context (ClearStateUponCompletion), чтобы не удерживать ссылки на lifted locals.",
                "В AsyncStateMachineBox.MoveNext есть проверка IsCompleted и вызов ClearStateUponCompletion.",
            ],
        )
    )

    body.append(_p("Мини-таблица: жизненный цикл state machine", bold=True, size_pt=16, space_before=240, space_after=120))
    body.append(
        _table(
            [
                ["Этап", "Что происходит в CoreLib"],
                ["Старт", "AsyncMethodBuilderCore.Start вызывает первый MoveNext() и восстанавливает контексты после него."],
                ["Suspend", "GetStateMachineBox создаёт Task+Box (если нужно), сохраняет ExecutionContext, регистрирует continuation на awaited task."],
                ["Resume", "Continuation вызывает box.MoveNext(), который запускает stateMachine.MoveNext() под сохранённым ExecutionContext."],
                ["Complete", "builder.SetResult/SetException завершает Task; box очищает состояние (ClearStateUponCompletion)."],
            ],
            header=True,
        )
    )

    body.append(_blank())
    _write_docx(output_path, title=title, body_inner="".join(body))


def build_risk_review_docx(output_path: str) -> None:
    title = "Async/await (CoreLib): потенциальные риски и компромиссы"
    subtitle = "Чеклист для ревью: хрупкие места, инварианты, архитектурные trade-offs"

    body: list[str] = []
    body.append(_p(title, bold=True, size_pt=24, center=True, space_after=100))
    body.append(_p(subtitle, size_pt=12, center=True, space_after=240))

    body.append(
        _section(
            "1. Хрупкие места (реальные источники регрессий)",
            [
                "Ниже перечислены участки, где ошибки обычно проявляются редко и сложно диагностируются: скрытые инварианты, ветки для отладки/ETW и предположения о layout.",
            ],
        )
    )

    body.append(_p("1.1 Unsafe.As и требования к layout (ABI-хрупкость)", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _table(
            [
                ["Тема", "Риск / почему важно"],
                [
                    "TaskAwaiter layout",
                    "TaskAwaiter и TaskAwaiter<TResult> должны иметь совместимую раскладку, т.к. используются Unsafe.As и приведения без копирования. Любое изменение полей/readonly/layout может сломать fast-path.",
                ],
                [
                    "ConfiguredTaskAwaiter layout",
                    "Аналогичные требования к layout существуют для ConfiguredTaskAwaiter. Регрессии здесь особенно неприятны: проявляются в редких сценариях и выглядят как «рандомные» падения/коррупция.",
                ],
            ],
            header=True,
        )
    )
    body.append(
        _p(
            "Ссылки: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/TaskAwaiter.cs:22, :288, :381, :463",
            size_pt=10,
            space_after=200,
        )
    )

    body.append(_p("1.2 Отказ от валидации ради perf (sharp edges)", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "TaskAwaiter сознательно не проверяет корректность инициализации «как публичный API». При неправильном использовании (в т.ч. руками, без компилятора) возможны NullReferenceException вместо предсказуемой ошибки. Это нормальный компромисс для compiler services, но источник неприятных падений при нетипичном использовании.",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(_p("Ссылка: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/TaskAwaiter.cs:11", size_pt=10, space_after=200))

    body.append(_p("1.3 Value-type builder: копирование и «два Task вместо одного»", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "AsyncTaskMethodBuilder<TResult> — struct. Если builder копировать до того, как зафиксировано единственное Task-экземпляр (через доступ к Task/SetResult/SetException), то разные копии могут построить разные Task. В обычном компиляторном сценарии это контролируется, но вокруг reflection/debugger-инструментов это типичный «край».",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(_p("Ссылка: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:16", size_pt=10, space_after=200))

    body.append(_p("1.4 ExecutionContext внутри Task.m_stateObject (инварианты и type-safety)", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "AsyncStateMachineBox хранит ExecutionContext в базовом Task.m_stateObject и скрывает его флагом HiddenState. Это эффективно, но требует строгого инварианта: поле должно быть только null или ExecutionContext. Нарушение этого инварианта — потенциальная дырища в type-safety и источник трудноотлавливаемых багов.",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(_p("Ссылка: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:334", size_pt=10, space_after=200))

    body.append(_p("1.5 Исключения при подписке continuation: уход в ThrowAsync", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "В местах, где awaiter может выкинуть исключение при регистрации continuation (OnCompleted/UnsafeOnCompleted), CoreLib предпочитает не пропускать это исключение обратно в async-метод на точке подвеса (это ломает модель state machine), а маршрутизировать его асинхронно через Task.ThrowAsync. Это корректно, но ухудшает диагностику для «кривых» кастомных awaiter’ов: стек/момент падения отделены от причины.",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(
        _p(
            "Ссылки: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:68, :131, :143",
            size_pt=10,
            space_after=240,
        )
    )

    body.append(
        _section(
            "2. Архитектурные компромиссы (не «ошибки», но важные trade-offs)",
            [
                "Эти решения обычно осознанны: они дают производительность и минимум аллокаций, но повышают связанность и сложность сопровождения.",
            ],
        )
    )

    body.append(_p("2.1 Box = Task + state machine", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "AsyncStateMachineBox<TStateMachine> одновременно является Task<TResult> и контейнером для state machine/ExecutionContext. Это уменьшает число объектов и ускоряет continuation path, но связывает async state machine с внутренностями TPL (Task continuation plumbing).",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(
        _p(
            "Ссылки: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncTaskMethodBuilderT.cs:279 и src/libraries/System.Private.CoreLib/src/System/Threading/Tasks/Task.cs:2485 / :2557",
            size_pt=10,
            space_after=200,
        )
    )

    body.append(_p("2.2 Legacy SetStateMachine (совместимость)", bold=True, size_pt=16, space_before=200, space_after=120))
    body.append(
        _p(
            "IAsyncStateMachine.SetStateMachine и соответствующий путь в AsyncMethodBuilderCore исторически требовались для старой модели бокса. В текущей реализации это в основном legacy: внутри CoreLib ожидается, что этот путь не используется (Debug.Fail).",
            size_pt=11,
            space_after=120,
        )
    )
    body.append(_p("Ссылка: src/libraries/System.Private.CoreLib/src/System/Runtime/CompilerServices/AsyncMethodBuilderCore.cs:72", size_pt=10, space_after=240))

    body.append(
        _section(
            "3. Практический чеклист для ревью/изменений",
            [
                "Если вы меняете код в этих файлах, проверьте следующие пункты до мержа.",
            ],
        )
    )
    body.append(
        _table(
            [
                ["Проверка", "Что может сломаться"],
                [
                    "Layout/Unsafe.As",
                    "Совместимость TaskAwaiter/ConfiguredTaskAwaiter fast-path; скрытые падения, некорректные приведения.",
                ],
                [
                    "Инвариант Context",
                    "Task.m_stateObject должен оставаться null/ExecutionContext; иначе риск type-safety.",
                ],
                [
                    "Ветки ETW/debugger",
                    "Редкие сценарии (debugger forcing Task до 1-го await, weakly-typed box) и неповторяемые баги.",
                ],
                [
                    "ContinueOnCapturedContext",
                    "Правильный маршаллинг continuation обратно в SynchronizationContext/TaskScheduler.",
                ],
                [
                    "Очистка состояния",
                    "ClearStateUponCompletion должен освобождать ссылки на lifted locals/контексты при завершении.",
                ],
            ],
            header=True,
        )
    )

    body.append(_blank())
    _write_docx(output_path, title=title, body_inner="".join(body))


# Back-compat alias
build_docx = build_overview_docx


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--kind",
        choices=["overview", "state-machine", "risk-review", "both", "all"],
        default="both",
        help="Which document(s) to generate.",
    )
    parser.add_argument(
        "--output-state-machine",
        default=os.path.join("docs", "async-state-machine-corelib.docx"),
        help="Output path for the state machine deep dive docx.",
    )
    parser.add_argument(
        "--output-overview",
        default=os.path.join("docs", "async-await-corelib.docx"),
        help="Output path for the overview docx.",
    )
    parser.add_argument(
        "--output-risk-review",
        default=os.path.join("docs", "async-await-corelib-risk-review.docx"),
        help="Output path for the risk review docx.",
    )
    args = parser.parse_args()

    if args.kind in ("overview", "both", "all"):
        build_overview_docx(args.output_overview)
    if args.kind in ("state-machine", "both", "all"):
        build_state_machine_docx(args.output_state_machine)
    if args.kind in ("risk-review", "all"):
        build_risk_review_docx(args.output_risk_review)
