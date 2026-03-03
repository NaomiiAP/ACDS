import os

def get_container_id(pid):
    """
    Reads /proc/<pid>/cgroup to extract the container ID if the process is running inside one.
    Avoids querying the Docker/containerd socket directly for security partitioning.
    """
    cgroup_path = f"/proc/{pid}/cgroup"
    
    if not os.path.exists(cgroup_path):
        return None

    try:
        with open(cgroup_path, "r") as f:
            for line in f:
                # Common markers for containerized environments
                if "docker" in line or "kubepods" in line or "containerd" in line:
                    # Example line: 1:name=systemd:/kubepods/burstable/podxxxx/abcd1234...
                    parts = line.strip().split("/")
                    container_layer = parts[-1]
                    
                    # Handle formats like kubepods-podxx...xx.slice:containerd:abcdef...
                    if "-" in container_layer and len(container_layer) > 64:
                        extracted = container_layer.split("-")[-1][:12]
                        if extracted:
                            return extracted
                    
                    # Return typical 12 chars of hex ID (standard short container ID)
                    if len(container_layer) >= 12:
                        return container_layer[:12]
    except Exception as e:
        # Failsafe: if we can't read it (e.g., due to permissions or race condition when process dies)
        pass
        
    return None
