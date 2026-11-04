#!/usr/bin/env python3
"""Read-only lexical UDP occurrence cross-check; never export vendor bodies.

Run once into a fresh directory. The fixed actual108 helper provides the same
four conditional-source selections, but the complete-identifier count below is
independent of its module/call/instance parsers. No simulation or qualification.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

STD_SHA = '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
HELPER_SHA = '53edd2c4da4e2a335d8332f7909918d43fc77dfd79078d96229f5a45bec30991'
TARGETS = ('udp_tlatrf', 'udp_tlatrf2')
MODES = (('actual_default', ()), ('FUNCTIONAL', ('FUNCTIONAL',)),
         ('functional', ('functional',)),
         ('both_functional_symbols', ('FUNCTIONAL', 'functional')))
IDENTIFIER = re.compile(r'\\[^\s]+|[A-Za-z_$][A-Za-z0-9_$]*')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def identity(path):
    path = Path(path).resolve()
    body = path.read_bytes()
    return dict(path=str(path), bytes=len(body), sha256=sha(body))


def write(path, obj):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')
    temporary.replace(path)


def clean_comments_strings(source):
    """Blank comments/strings, retain line/column positions and escaped names.

    Recognizing an escaped identifier before slash/comment syntax prevents a
    legal name containing //, /*, or a quote from hiding a target occurrence.
    """
    result = list(source)
    index = 0
    while index < len(source):
        if source[index] == '\\' and index + 1 < len(source) and not source[index + 1].isspace():
            index += 1
            while index < len(source) and not source[index].isspace():
                index += 1
            continue
        end = None
        if source.startswith('//', index):
            end = source.find('\n', index + 2)
            end = len(source) if end == -1 else end
        elif source.startswith('/*', index):
            close = source.find('*/', index + 2)
            need(close != -1, 'unterminated source block comment')
            end = close + 2
        elif source[index] == '"':
            end = index + 1
            closed = False
            while end < len(source):
                if source[end] == '\\':
                    end += 2
                elif source[end] == '"':
                    end += 1
                    closed = True
                    break
                else:
                    end += 1
            need(closed, 'unterminated source string')
        if end is not None:
            for cursor in range(index, end):
                if source[cursor] != '\n':
                    result[cursor] = ' '
            index = end
        else:
            index += 1
    return ''.join(result)


def count_occurrences(cleaned, label, defines):
    """Every complete name, not just parser-recognized named instantiations."""
    matches = list(IDENTIFIER.finditer(cleaned))
    records = {name: [] for name in TARGETS}
    previous_name = None
    previous_end = None
    for match in matches:
        raw = match.group()
        normalized = raw[1:] if raw.startswith('\\') else raw
        if normalized in records:
            # Only whitespace may intervene between the primitive keyword and
            # its declaration name. This does not parse or assume a caller form.
            declaration = previous_name == 'primitive' and cleaned[previous_end:match.start()].strip() == ''
            records[normalized].append(dict(line=cleaned.count('\n', 0, match.start()) + 1,
                                             primitive_definition_name=declaration,
                                             escaped_identifier=raw.startswith('\\')))
        previous_name, previous_end = normalized, match.end()
    result = []
    for name in TARGETS:
        occurrences = records[name]
        definitions = [row for row in occurrences if row['primitive_definition_name']]
        others = [row for row in occurrences if not row['primitive_definition_name']]
        result.append(dict(name=name, total_identifier_occurrences=len(occurrences),
                           primitive_definition_count=len(definitions),
                           occurrence_lines=[row['line'] for row in occurrences],
                           primitive_definition_lines=[row['line'] for row in definitions],
                           escaped_occurrence_count=sum(row['escaped_identifier'] for row in occurrences),
                           nondefinition_occurrence_count=len(others),
                           nondefinition_occurrence_lines=[row['line'] for row in others],
                           no_other_lexical_reference_in_this_selected_source=(
                               len(occurrences) == len(definitions) and len(definitions) > 0)))
    return dict(mode=label, additional_defines=list(defines),
                clean_source_bytes=len(cleaned.encode()), clean_source_sha256=sha(cleaned.encode()),
                all_identifier_token_count=len(matches), targets=result)


def run(args):
    base = args.base.resolve()
    source_path = base / 'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v'
    helper_path = args.helper.resolve()
    out = args.out.resolve() if args.out else base / 'mapped-udp-occurrence-20261104-113'
    need(not out.exists(), 'fresh actual113 output required; original results must not be overwritten')
    out.mkdir(parents=True)
    inputs = [source_path, helper_path, Path(__file__).resolve()]
    state = dict(status='RUNNING_READONLY_LEXICAL_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                 started_epoch=time.time(), input_sha256_before=[identity(path) for path in inputs],
                 vendor_body_exported=False,
                 limitations=[
                     'Only the fixed ordinary standard-cell source and the four listed conditional selections are counted.',
                     'This cross-check does not use the actual108 module, primitive-caller or instance parsers.',
                     'The same hash-frozen actual108 conditional preprocessor is used; this is not an independent full Verilog preprocessor.',
                     'A zero nondefinition count means no other lexical reference in that selected source, not global runtime or design nonuse.',
                     'Macro token concatenation, external files and other compile configurations are outside this lexical conclusion.',
                     'No source modification, primitive replacement, simulator run, timing or functional qualification is performed.'])
    write(out / 'state.json', state)
    try:
        need(state['input_sha256_before'][0]['sha256'] == STD_SHA, 'fixed original standard-cell SHA differs')
        need(state['input_sha256_before'][1]['sha256'] == HELPER_SHA, 'fixed actual108 helper SHA differs')
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('xu_udp_review108_readonly113', str(helper_path))
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        source = source_path.read_bytes().decode('utf-8')
        cleaned = clean_comments_strings(source)
        reports = [count_occurrences(cleaned, 'full_clean_source_no_conditional_selection', ())]
        for name, defines in MODES:
            selected = helper.preprocess(cleaned, defines)
            need(selected.count('\n') == source.count('\n'), 'preprocessor changed line numbering')
            reports.append(count_occurrences(selected, name, defines))
        report = dict(status='LEXICAL_COUNTS_ONLY_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                      source_identity=state['input_sha256_before'][0],
                      preprocessing_helper_identity=state['input_sha256_before'][1],
                      modes=reports, vendor_body_exported=False,
                      no_other_lexical_reference_in_all_five_sources=all(
                          target['no_other_lexical_reference_in_this_selected_source']
                          for mode in reports for target in mode['targets']))
        write(out / 'occurrences.json', report)
        state['report'] = identity(out / 'occurrences.json')
        state['status'] = 'EXECUTED_READONLY_LEXICAL_COUNTS_NOT_QUALIFIED'
    except BaseException as error:
        state['status'] = 'FAILED_READONLY_LEXICAL_COUNTS_NOT_QUALIFIED'
        state['error_type'] = type(error).__name__
        # Do not include exception text, which could contain a vendor source body.
    finally:
        state['input_sha256_after'] = [identity(path) for path in inputs]
        state['inputs_unchanged'] = state['input_sha256_before'] == state['input_sha256_after']
        if not state['inputs_unchanged']:
            state['status'] = 'FAILED_INPUT_IDENTITY_CHANGED_NOT_QUALIFIED'
        state['finished_epoch'] = time.time()
        write(out / 'state.json', state)
    if state['status'] != 'EXECUTED_READONLY_LEXICAL_COUNTS_NOT_QUALIFIED':
        print('XU_UDP113_FAILED', state['status'], state.get('error_type', 'INPUT_CHANGED'), flush=True)
        return 1
    print('XU_UDP113_DONE', state['status'], state['report']['sha256'], flush=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'Desktop/xu-score-optimization-20261102')
    parser.add_argument('--helper', type=Path, default=Path.home() / 'Desktop/xu_udp_review108.py')
    parser.add_argument('--out', type=Path)
    sys.exit(run(parser.parse_args()))
