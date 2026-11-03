"""Reproduce the bounded, post-run feature-identity checks without inference.

These checks were not performed before the experiments. They cannot make the
Spambase audit vector-disjoint retrospectively, and do not inspect all training
or historical candidate-pool rows. No output files or per-row values are emitted.
"""
import csv
import math
import run as r


def features(path, id_field):
    with open(path) as f:
        reader = csv.DictReader(f)
        columns = sorted((k for k in reader.fieldnames if k.startswith('x_')),
                         key=lambda k: int(k[2:]))
        ids, vectors = [], []
        for row in reader:
            vector = tuple(float(row[k]) for k in columns)
            assert all(math.isfinite(x) for x in vector)
            ids.append(row[id_field])
            vectors.append(vector)
    return ids, vectors


def check():
    a = r.read(r.RUN/'A3_INPUT_SEPARATION_CHECK.json')
    for item in a['checks']:
        paths = list(item['source_files'])
        for p, h in item['source_files'].items():
            assert r.sha(p) == h
        ids, vv = features(paths[0], 'row_id')
        aid, av = features(paths[1], 'row_id')
        overlap = set(vv) & set(av)
        actual = {
            'candidate_rows': len(vv), 'audit_rows': len(av),
            'feature_dimensions': len(vv[0]),
            'source_row_id_intersection': len(set(ids) & set(aid)),
            'candidate_distinct_model_input_vectors': len(set(vv)),
            'audit_distinct_model_input_vectors': len(set(av)),
            'shared_model_input_vectors': len(overlap),
            'candidate_rows_with_shared_vector': sum(v in overlap for v in vv),
            'audit_rows_with_shared_vector': sum(v in overlap for v in av),
        }
        for key, value in actual.items():
            assert item[key] == value, (item['case'], key, item[key], value)
        for sub in a['subset_checks']:
            if sub['case'] != item['case']:
                continue
            p = r.RUN/'inputs'/item['case']/(
                f"order{sub['order']}_n{sub['selection_source_rows']}.prepared")/'prepared.csv'
            _, sv = features(p, 'row_id')
            shared = set(sv) & set(av)
            actual = {
                'selection_source_rows': len(sv),
                'distinct_selection_vectors': len(set(sv)),
                'shared_vectors_with_old_audit': len(shared),
                'selection_rows_matching_old_audit_vector': sum(v in shared for v in sv),
                'old_audit_rows_matching_selection_vector': sum(v in shared for v in av),
            }
            for key, value in actual.items():
                assert sub[key] == value, (item['case'], sub['order'], key)
    b = r.read(r.RUN/'BANK_INPUT_IDENTITY_CHECK.json')
    oldids, oldv, newids, newv = [], [], [], []
    for p, h in b['files'].items():
        assert r.sha(p) == h
        ids, vv = features(p, 'source_row_id')
        if '/inputs/reserved684/' in p:
            newids.extend(ids); newv.extend(vv)
        else:
            oldids.extend(ids); oldv.extend(vv)
    shared = set(oldv) & set(newv)
    actual = {
        'old_selection_development_audit_rows': len(oldv),
        'reserved_rows': len(newv),
        'original_source_row_intersection': len(set(oldids) & set(newids)),
        'old_distinct_vectors': len(set(oldv)),
        'reserved_distinct_vectors': len(set(newv)),
        'shared_vectors': len(shared),
        'reserved_rows_matching_old_vectors': sum(v in shared for v in newv),
    }
    for key, value in actual.items():
        assert b[key] == value, (key, b[key], value)
    return {'A3_pool_checks': len(a['checks']),
            'A3_subset_checks': len(a['subset_checks']),
            'Bank_bounded_identity_check': 'verified',
            'interpretation': 'post-run descriptive only; no inference or writes'}


if __name__ == '__main__':
    print(check())
