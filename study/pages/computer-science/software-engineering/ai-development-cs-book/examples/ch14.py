"""A claim audit demonstrates an unsupported completion claim is rejected."""
import json


def audit(claims, evidence):
    return [claim for claim in claims if claim not in evidence or evidence[claim]['status'] != 'passed']


def main():
    evidence = {'unit-policy': {'status': 'passed', 'command': 'python ch03.py'},
                'restart-recovery': {'status': 'not-run', 'command': None}}
    assert audit(['unit-policy'], evidence) == []
    assert audit(['unit-policy', 'restart-recovery', '1500-person-load'], evidence) == [
        'restart-recovery', '1500-person-load']
    print(json.dumps({'supported_claims': ['unit-policy'],
                      'unsupported_claims_rejected': ['restart-recovery', '1500-person-load'],
                      'note': 'Evidence labels are fictional fixtures, not a service certification.'}))


if __name__ == '__main__':
    main()
