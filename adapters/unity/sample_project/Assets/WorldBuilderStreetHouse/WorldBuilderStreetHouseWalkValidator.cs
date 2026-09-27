using System;
using System.IO;
using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public sealed class WorldBuilderStreetHouseWalkValidator : MonoBehaviour
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
        public string source_id;
        public string geometry_sha256;
        public string status = "in_progress";
        public string reason;
        public int grounded_frames;
        public int stair_supported_frames;
        public int side_collision_frames;
        public string first_side_collider;
        public float duration_seconds;
        public Vector3 final_position;
        public Checkpoint[] checkpoints;
    }

    public string sourceId;
    public string geometryHash;
    private static readonly Vector3[] Targets = {
        new Vector3(8.5f, 1.9f, 1.5f),
        new Vector3(8.5f, 1.9f, 4.5f),
        new Vector3(8.5f, 1.9f, 6.5f),
        new Vector3(13.5f, 1.9f, 5.5f),
        new Vector3(13.5f, 5.9f, 10.5f),
        new Vector3(10.5f, 5.9f, 8.5f)
    };
    private static readonly string[] Names = {
        "street", "south_entry", "shop", "stair_foot", "upper_landing", "upper_room"
    };

    private CharacterController controller;
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
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_STREET_HOUSE_WALK_RESULT");
        if (string.IsNullOrEmpty(outputPath))
            throw new InvalidOperationException("walk result path is required");
        result = new Result {
            unity_version = Application.unityVersion,
            source_id = sourceId,
            geometry_sha256 = geometryHash,
            checkpoints = new Checkpoint[Targets.Length]
        };
        Save();
    }

    private void Update()
    {
        if (result.status != "in_progress") return;
        float stepSeconds = Mathf.Max(Time.deltaTime, 1f / 120f);
        simulatedSeconds += stepSeconds;
        if (simulatedSeconds > 50f) { Finish("failed", "route_timeout"); return; }
        Vector3 target = Targets[targetIndex];
        Vector3 current = transform.position;
        Vector3 horizontal = new Vector3(target.x - current.x, 0f, target.z - current.z);
        float distance = horizontal.magnitude;
        if (distance < bestDistance - .02f)
        {
            bestDistance = distance;
            lastProgressSeconds = simulatedSeconds;
        }
        if (distance < .22f && Mathf.Abs(current.y - target.y) < .35f && controller.isGrounded)
        {
            result.checkpoints[targetIndex] = new Checkpoint {
                name = Names[targetIndex], position = current, elapsed_seconds = simulatedSeconds
            };
            targetIndex++;
            Save();
            if (targetIndex == Targets.Length)
            {
                Finish(result.grounded_frames > 30 && result.stair_supported_frames > 4 ? "pass" : "failed",
                       "continuous_entry_stair_upper_room_route");
                return;
            }
            bestDistance = float.PositiveInfinity;
            lastProgressSeconds = simulatedSeconds;
            return;
        }
        if (simulatedSeconds - lastProgressSeconds > 7f)
        {
            Finish("failed", "stalled_at_" + Names[targetIndex]); return;
        }
        if (controller.isGrounded && verticalSpeed < 0f) verticalSpeed = -1f;
        else verticalSpeed += Physics.gravity.y * stepSeconds;
        Vector3 movement = horizontal.normalized * Mathf.Min(1.9f * stepSeconds, distance);
        movement.y = verticalSpeed * stepSeconds;
        CollisionFlags flags = controller.Move(movement);
        if ((flags & CollisionFlags.Below) != 0) result.grounded_frames++;
        if ((flags & CollisionFlags.Sides) != 0) result.side_collision_frames++;
        if ((flags & CollisionFlags.Below) != 0 &&
            transform.position.x >= 12f && transform.position.x <= 15f &&
            transform.position.z >= 6f && transform.position.z <= 10f &&
            transform.position.y > 2f && transform.position.y < 6f)
            result.stair_supported_frames++;
    }

    private void OnDisable()
    {
        if (result != null && result.status == "in_progress") Finish("interrupted", "play_mode_stopped");
    }

    private void OnControllerColliderHit(ControllerColliderHit hit)
    {
        if (result != null && string.IsNullOrEmpty(result.first_side_collider) &&
            Mathf.Abs(hit.normal.y) < .5f)
            result.first_side_collider = hit.collider.name + " bounds=" + hit.collider.bounds;
    }

    private void Finish(string status, string reason)
    {
        result.status = status;
        result.reason = reason;
        result.duration_seconds = simulatedSeconds;
        result.final_position = transform.position;
        Save();
        Debug.Log("WorldBuilder street house walk: " + status + " (" + reason + ")");
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
