using System;
using System.IO;
using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public sealed class WorldBuilderOpenSpaceWalkValidator : MonoBehaviour
{
    [Serializable] private sealed class Checkpoint
    {
        public string name;
        public Vector3 position;
        public float elapsed_seconds;
    }

    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string source_id;
        public string scene;
        public string status;
        public string reason;
        public int grounded_frames;
        public int path_surface_frames;
        public int side_collision_frames;
        public float max_lateral_error_m;
        public float simulated_duration_seconds;
        public Vector3 final_position;
        public string last_support_collider;
        public Checkpoint[] checkpoints;
    }

    public string sourceWorldId;
    public string sourceRevisionId;
    public string sourceId;

    private readonly Vector3[] targets = {
        new Vector3(308.811f, 1.3f, 210f),
        new Vector3(308.811f, 1.3f, 223f),
        new Vector3(308.811f, 1.3f, 237f)
    };
    private readonly string[] names = { "south_path", "middle_path", "north_path" };
    private CharacterController controller;
    private Transform path;
    private Result result;
    private string outputPath;
    private int targetIndex;
    private float verticalSpeed;
    private float simulatedSeconds;
    private float lastProgressSeconds;
    private float bestDistance = float.PositiveInfinity;

    private void Start()
    {
        controller = GetComponent<CharacterController>();
        var pathObject = GameObject.Find(sourceId + "_path");
        if (pathObject == null) throw new InvalidOperationException("source path node missing");
        path = pathObject.transform;
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_OPEN_SPACE_WALK_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            throw new InvalidOperationException("WORLD_BUILDER_UNITY_OPEN_SPACE_WALK_VALIDATION is required");
        result = new Result {
            unity_version = Application.unityVersion,
            source_world_id = sourceWorldId,
            source_revision_id = sourceRevisionId,
            source_id = sourceId,
            scene = gameObject.scene.name,
            status = "in_progress",
            reason = "",
            checkpoints = new Checkpoint[targets.Length]
        };
        Save();
    }

    private void Update()
    {
        if (result.status != "in_progress") return;
        var stepSeconds = Mathf.Max(Time.deltaTime, 1f / 120f);
        simulatedSeconds += stepSeconds;
        if (simulatedSeconds > 30f) { Finish("failed", "route_timeout"); return; }
        var current = transform.position;
        var target = targets[targetIndex];
        var horizontal = new Vector3(target.x - current.x, 0f, target.z - current.z);
        var distance = horizontal.magnitude;
        if (distance < bestDistance - 0.02f) {
            bestDistance = distance;
            lastProgressSeconds = simulatedSeconds;
        }
        if (distance < 0.15f && Mathf.Abs(current.y - target.y) < 0.25f && controller.isGrounded) {
            result.checkpoints[targetIndex] = new Checkpoint {
                name = names[targetIndex], position = current,
                elapsed_seconds = simulatedSeconds
            };
            targetIndex++;
            if (targetIndex == targets.Length) {
                Finish(result.grounded_frames >= 50 && result.path_surface_frames >= 50 &&
                       result.side_collision_frames == 0 ? "pass" : "failed",
                       "continuous_character_controller_path");
                return;
            }
            bestDistance = float.PositiveInfinity;
            lastProgressSeconds = simulatedSeconds;
            Save();
            return;
        }
        if (simulatedSeconds - lastProgressSeconds > 5f) {
            Finish("failed", "stalled_at_" + names[targetIndex]); return;
        }
        // Batchmode can render far faster than the controller's movement threshold.
        if (controller.isGrounded && verticalSpeed < 0f) verticalSpeed = -1f;
        else verticalSpeed += Physics.gravity.y * stepSeconds;
        var movement = horizontal.normalized * Mathf.Min(2.4f * stepSeconds, distance);
        movement.y = verticalSpeed * stepSeconds;
        var flags = controller.Move(movement);
        if ((flags & CollisionFlags.Below) != 0) result.grounded_frames++;
        if ((flags & CollisionFlags.Sides) != 0) result.side_collision_frames++;
        result.max_lateral_error_m = Mathf.Max(result.max_lateral_error_m,
            Mathf.Abs(transform.position.x - targets[0].x));
        foreach (var hit in Physics.RaycastAll(transform.position, Vector3.down, 1.5f)) {
            result.last_support_collider = hit.collider.name;
            if (hit.transform == path || hit.transform.IsChildOf(path)) {
                result.path_surface_frames++;
                break;
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
        result.simulated_duration_seconds = simulatedSeconds;
        result.final_position = transform.position;
        Save();
        Debug.Log("WorldBuilder open space walk: " + status + " (" + reason + ")");
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
