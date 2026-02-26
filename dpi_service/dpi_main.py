from packet_capture import start_capture
from flow_manager import add_packet, flows, get_expired_flows
from feature_extractor import extract_features

FLOW_LIMIT = 20


def process_packet(packet):

    key = add_packet(packet)

    if key is None:
        return

    if len(flows[key]) >= FLOW_LIMIT:

        features = extract_features(flows[key])

        print("\nFEATURE VECTOR:")
        print(features)

        flows[key] = []

    expired = get_expired_flows()

    for exp_key in expired:

        if exp_key in flows and len(flows[exp_key]) > 5:

            features = extract_features(flows[exp_key])

            print("\nFLOW TIMEOUT FEATURES:")
            print(features)

        flows.pop(exp_key, None)


if __name__ == "__main__":
    print("DPI STARTING...")
    start_capture(process_packet)