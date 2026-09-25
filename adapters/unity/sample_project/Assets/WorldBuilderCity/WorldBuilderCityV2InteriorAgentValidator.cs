using System;
using System.IO;
using UnityEngine;
using UnityEngine.AI;

[RequireComponent(typeof(NavMeshAgent))]
public sealed class WorldBuilderCityV2InteriorAgentValidator : MonoBehaviour
{
    [Serializable] private sealed class Result
    {
        public string status = "in_progress";
        public string reason;
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string source_building_id = "building_000";
        public string scene;
        public int agent_type_id;
        public float agent_radius_m;
        public float agent_height_m;
        public float elapsed_seconds;
        public int movement_frames;
        public int door_link_frames;
        public int door_link_moving_frames;
        public int stair_supported_moving_frames;
        public float travel_distance_m;
        public float door_link_distance_m;
        public float stair_supported_distance_m;
        public string end_support_source_id;
        public int off_navmesh_frames;
        public float max_frame_step_m;
        public float max_height_m;
        public bool crossed_east_door;
        public bool ascended_stair;
        public string path_status;
        public Vector3 start_position;
        public Vector3 door_position;
        public Vector3 stair_high_position;
        public Vector3 end_position;
    }

    public string sourceWorldId;
    public string sourceRevisionId;

    private readonly Vector3 start = new Vector3(34f, 2f, 16.5f);
    private readonly Vector3 goal = new Vector3(25.5f, 5.2f, 26f);
    private NavMeshAgent agent;
    private Result result;
    private string outputPath;
    private float startedAt;
    private float lastProgressAt;
    private float bestRemaining = float.PositiveInfinity;
    private Vector3 previous;
    private Vector3 lastSupportSamplePosition;

    private void Start()
    {
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V2_INTERIOR_AGENT_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            outputPath = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v2-interior-agent-validation.json"));
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
        startedAt = Time.time;
        NavMeshHit startHit;
        NavMeshHit goalHit;
        if (!NavMesh.SamplePosition(start, out startHit, 0.6f, NavMesh.AllAreas) ||
            !NavMesh.SamplePosition(goal, out goalHit, 0.6f, NavMesh.AllAreas))
        {
            Finish("failed", "missing_start_or_room_navmesh");
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
        result.max_height_m = transform.position.y;
        previous = transform.position;
        lastSupportSamplePosition = previous;
        lastProgressAt = Time.time;
        Save();
    }

    private void Update()
    {
        if (result == null || result.status != "in_progress") return;
        result.elapsed_seconds = Time.time - startedAt;
        if (result.elapsed_seconds > 40f) { Finish("failed", "route_timeout"); return; }
        if (!agent.isOnNavMesh) { result.off_navmesh_frames++; Finish("failed", "agent_left_navmesh"); return; }
        var current = transform.position;
        var step = Vector3.Distance(previous, current);
        result.max_frame_step_m = Mathf.Max(result.max_frame_step_m, step);
        if (step > 0.75f) { Finish("failed", "agent_teleported"); return; }
        result.travel_distance_m += step;
        var supportSampleDistance = Vector3.Distance(lastSupportSamplePosition, current);
        if (supportSampleDistance >= 0.05f)
        {
            RecordStairSupport(lastSupportSamplePosition, current, supportSampleDistance);
            lastSupportSamplePosition = current;
        }
        var moved = step > 0.001f;
        if (moved)
            result.movement_frames++;
        if (agent.isOnOffMeshLink)
        {
            result.door_link_frames++;
            result.door_link_distance_m += step;
            if (moved)
                result.door_link_moving_frames++;
        }
        if (!result.crossed_east_door && previous.x >= 32f && current.x < 32f &&
            current.z >= 16f && current.z <= 18f && current.y >= 1.9f && current.y <= 2.5f)
        {
            result.crossed_east_door = true;
            result.door_position = current;
        }
        if (!result.ascended_stair && current.y >= 4.5f && current.x >= 27f &&
            current.x <= 30f && current.z >= 17f && current.z <= 27.5f)
        {
            result.ascended_stair = true;
            result.stair_high_position = current;
        }
        result.max_height_m = Mathf.Max(result.max_height_m, current.y);
        previous = current;
        if (!agent.pathPending)
        {
            result.path_status = agent.pathStatus.ToString();
            if (!agent.isOnOffMeshLink && agent.pathStatus != NavMeshPathStatus.PathComplete)
            {
                Finish("failed", "agent_path_incomplete");
                return;
            }
            if (agent.remainingDistance < bestRemaining - 0.05f)
            {
                bestRemaining = agent.remainingDistance;
                lastProgressAt = Time.time;
            }
            if (Time.time - lastProgressAt > 8f) { Finish("failed", "agent_stalled"); return; }
            var horizontalDistance = Vector2.Distance(new Vector2(current.x, current.z),
                new Vector2(goal.x, goal.z));
            if (agent.remainingDistance <= agent.stoppingDistance + 0.08f &&
                horizontalDistance < 0.35f && Mathf.Abs(current.y - 5.2f) < 0.3f)
            {
                result.end_position = current;
                RaycastHit roomSupport;
                if (Physics.Raycast(current + Vector3.up * 0.2f, Vector3.down,
                    out roomSupport, 0.8f))
                {
                    var source = roomSupport.collider.GetComponentInParent<WorldBuilderSourceId>();
                    if (source != null) result.end_support_source_id = source.sourceId;
                }
                if (!result.crossed_east_door || !result.ascended_stair ||
                    result.door_link_distance_m < 0.5f ||
                    result.stair_supported_distance_m < 1f ||
                    result.travel_distance_m < 15f ||
                    result.end_support_source_id != "storey_000_1")
                    Finish("failed", "insufficient_continuous_door_stair_motion");
                else Finish("pass", "agent_entered_and_ascended_on_saved_navmesh");
            }
        }
    }

    private void RecordStairSupport(Vector3 from, Vector3 to, float distance)
    {
        var count = Mathf.Max(1, Mathf.CeilToInt(distance / 0.1f));
        var supported = false;
        for (var i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(from, to, (i + 0.5f) / count);
            if (point.x < 27f || point.x > 30f || point.z < 17f || point.z > 27.5f ||
                point.y < 2.2f || point.y > 5.35f)
                continue;
            RaycastHit hit;
            if (!Physics.Raycast(point + Vector3.up * 0.2f, Vector3.down, out hit, 0.8f))
                continue;
            var source = hit.collider.GetComponentInParent<WorldBuilderSourceId>();
            if (source == null || source.sourceId != "stair_000") continue;
            result.stair_supported_distance_m += distance / count;
            supported = true;
        }
        if (supported) result.stair_supported_moving_frames++;
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
        Debug.Log("WorldBuilder first city interior agent walk: " + status +
            " (" + reason + ") at " + transform.position);
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
