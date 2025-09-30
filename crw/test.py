from scorer import *
from config import *
from downloader import *
import logging

def checker_generic(predicted: dict, expected: dict, field: str, pos: str, neg: str) -> dict:
    tp = fp = fn = tn = 0

    for k, expected_val in expected.items():
        pred_val = predicted.get(k, {}).get('model_answer')
        exp_val = expected_val.get(field)

        if exp_val == pos:
            if pred_val == pos:
                tp += 1
            else:
                fn += 1
        elif exp_val == neg:
            if pred_val == neg:
                tn += 1
            else:
                fp += 1

    return {'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn}

def test():
    full_data = get_results_from_json(configGS['dataset'])
    already_processed = get_results_from_json(configGS['filtered'])
    successful = {}

    for announcement_id, entry in full_data.items():
        if announcement_id in already_processed:
            continue
        already_processed[announcement_id] = {'name': entry['name']}
        result1 = request_to_model(entry['name'])
        entry['result1'] = result1
        logging.info(f"{announcement_id}: model1 result — {result1}")
        if result1 == 'возможно':
            process_by_announcement_id(announcement_id)
            result2 = final_score(announcement_id)
            entry['result2'] = result2
            logging.info(f"{announcement_id}: model2 result =  {result2}")
    expected_data = get_results_from_json(configGS['dataset'])

    print("Model 1 (возможно/нет):", checker_generic(full_data, expected_data, 'result1', 'возможно', 'нет'))

    save_results_to_json(successful, configGS['stage2s'])
    save_results_to_json(already_processed, configGS['filtered'])
    save_results_to_json(full_data, model_name+'new.json')

if __name__ == "__main__":
    test()
