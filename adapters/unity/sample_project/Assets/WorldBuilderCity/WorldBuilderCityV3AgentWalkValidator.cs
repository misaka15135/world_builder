using System;
using System.IO;
using UnityEngine;
using UnityEngine.AI;

[RequireComponent(typeof(NavMeshAgent))]
public sealed class WorldBuilderCityV3AgentWalkValidator : MonoBehaviour
{
    [Serializable] private sealed class Result
    {
        public string status = "in_progress";
        public string reason;
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string scene;
        public int agent_type_id;
        public float agent_radius_m;
        public float agent_height_m;
        public float elapsed_seconds;
        public int movement_frames;
        public int bridge_frames;
        public int bridge_moving_frames;
        public int bridge_support_frames;
        public int bridge_support_moving_frames;
        public int off_navmesh_frames;
        public float max_frame_step_m;
        public bool crossed_bridge_center;
        public string path_status;
        public Vector3 start_position;
        public Vector3 bridge_position;
        public Vector3 end_position;
    }

    public string sourceWorldId;
    public string sourceRevisionId;

    private readonly Vector3 start = new Vector3(244f, 2f, 271f);
    private readonly Vector3 goal = new Vector3(268f, 2f, 271f);
    private NavMeshAgent agent;
    private Result result;
    private string outputPath;
    private float startedAt;
    private float lastProgressAt;
    private float bestRemaining = float.PositiveInfinity;
    private Vector3 previous;

    private void Start()
    {
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V3_AGENT_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            outputPath = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v3-agent-walk-validation.json"));
        agent = GetComponent<NavMeshAgent>();
        result = new Result {
            unity_version = Application.unityVersion,
            source_world_id = sourceWorldId,
            source_revision_id = sourceRevisionId,
            scene = gameObject.scene.name,
            agent_type_id = agent.agentTypeID,
            agent_radius_m = agent.radius,
            agent_height_m = agent.height
        };
        NavMeshHit startHit;
        NavMeshHit goalHit;
        if (!NavMesh.SamplePosition(start, out startHit, 1f, NavMesh.AllAreas) ||
            !NavMesh.SamplePosition(goal, out goalHit, 1f, NavMesh.AllAreas))
        {
            Finish("failed", "missing_start_or_goal_navmesh");
            return;
        }
        transform.position = startHit.position;
        agent.enabled = true;
        if (!agent.isOnNavMesh || !agent.Warp(startHit.position) || !agent.SetDestination(goalHit.position))
        {
            Finish("failed", "agent_could_not_start");
            return;
        }
        result.start_position = transform.position;
        previous = transform.position;
        startedAt = Time.time;
        lastProgressAt = Time.time;
        Save();
    }

    private void Update()
    {
        if (result == null || result.status != "in_progress") return;
        result.elapsed_seconds = Time.time - startedAt;
        if (result.elapsed_seconds > 25f) { Finish("failed", "route_timeout"); return; }
        if (!agent.isOnNavMesh) { result.off_navmesh_frames++; Finish("failed", "agent_left_navmesh"); return; }
        var current = transform.position;
        result.max_frame_step_m = Mathf.Max(result.max_frame_step_m, Vector3.Distance(previous, current));
        if (result.max_frame_step_m > 0.5f) { Finish("failed", "agent_teleported"); return; }
        var moved = Vector3.Distance(previous, current) > 0.001f;
        if (moved) result.movement_frames++;
        if (current.x >= 252.25f && current.x <= 259.75f &&
            Mathf.Abs(current.y - 2f) < 0.3f && Mathf.Abs(current.z - 271f) < 0.6f)
        {
            result.bridge_frames++;
            if (moved) result.bridge_moving_frames++;
            RaycastHit support;
            if (Physics.Raycast(current + Vector3.up * 0.2f, Vector3.down, out support, 0.7f))
            {
                var source = support.collider.GetComponentInParent<WorldBuilderSourceId>();
                if (source != null && source.sourceId == "bridge_main")
                {
                    result.bridge_support_frames++;
                    if (moved) result.bridge_support_moving_frames++;
                }
            }
        }
        if (!result.crossed_bridge_center && previous.x <= 256f && current.x >= 256f &&
            Mathf.Abs(current.z - 271f) < 0.6f && Mathf.Abs(current.y - 2f) < 0.3f)
        {
            result.crossed_bridge_center = true;
            result.bridge_position = current;
        }
        previous = current;
        if (!agent.pathPending)
        {
            result.path_status = agent.pathStatus.ToString();
            if (agent.pathStatus != NavMeshPathStatus.PathComplete)
            {
                Finish("failed", "agent_path_incomplete");
                return;
            }
            if (agent.remainingDistance < bestRemaining - 0.05f)
            {
                bestRemaining = agent.remainingDistance;
                lastProgressAt = Time.time;
            }
            if (Time.time - lastProgressAt > 5f) { Finish("failed", "agent_stalled"); return; }
            if (agent.remainingDistance <= agent.stoppingDistance + 0.08f &&
                Vector3.Distance(new Vector3(current.x, 0f, current.z), new Vector3(goal.x, 0f, goal.z)) < 0.35f)
            {
                result.end_position = current;
                if (!result.crossed_bridge_center || result.bridge_moving_frames < 5 ||
                    result.bridge_support_moving_frames < 5 || result.movement_frames < 30)
                    Finish("failed", "insufficient_continuous_bridge_motion");
                else Finish("pass", "agent_crossed_bridge_on_saved_navmesh");
            }
        }
    }

    private void OnDisable()
    {
        if (result != null && result.status == "in_progress") Finish("interrupted", "play_mode_stopped");
    }

    private void Finish(string status, string reason)
    {
        result.status = status;
        result.reason = reason;
        result.elapsed_seconds = Time.time - startedAt;
        if (agent != null && agent.isOnNavMesh) result.end_position = transform.position;
        Save();
        Debug.Log("WorldBuilder city v3 agent walk: " + status + " (" + reason +
            ") at " + transform.position);
#if UNITY_EDITOR
        if (Application.isBatchMode) UnityEditor.EditorApplication.Exit(status == "pass" ? 0 : 1);
#endif
    }

    private void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));
        File.WriteAllText(outputPath, JsonUtility.ToJson(result, true));
    }
}
