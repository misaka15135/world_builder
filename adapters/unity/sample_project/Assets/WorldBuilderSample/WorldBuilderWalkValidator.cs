using System;
using System.Collections;
using System.IO;
using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public sealed class WorldBuilderWalkValidator : MonoBehaviour
{
    [Serializable] private sealed class Checkpoint
    {
        public string name;
        public float x;
        public float y;
        public float z;
        public float elapsed_seconds;
    }

    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string scene;
        public string status;
        public string reason;
        public float player_height;
        public float player_radius;
        public float step_offset;
        public int grounded_frames;
        public int side_collision_frames;
        public string screenshot;
        public Checkpoint[] checkpoints;
    }

    private readonly Vector3[] targets = {
        new Vector3(14f, 0.2f, 4.5f),
        new Vector3(17f, 0.2f, 6.5f),
        new Vector3(17f, 0.2f, 7.8f),
        new Vector3(17f, 4.2f, 12.7f),
        new Vector3(14f, 4.2f, 14f)
    };
    private readonly string[] names = { "through_south_door", "lower_room", "stair_foot", "upper_landing", "upper_room" };
    private CharacterController controller;
    private Result result;
    private int targetIndex;
    private float verticalSpeed;
    private float startedAt;
    private float lastProgressAt;
    private float bestDistance = float.PositiveInfinity;
    private string outputPath;

    private void Start()
    {
        controller = GetComponent<CharacterController>();
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_WALK_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            outputPath = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-sample/walk-validation.json"));
        result = new Result {
            unity_version = Application.unityVersion,
            scene = gameObject.scene.name,
            status = "in_progress",
            reason = "",
            player_height = controller.height,
            player_radius = controller.radius,
            step_offset = controller.stepOffset,
            checkpoints = new Checkpoint[targets.Length]
        };
        startedAt = Time.time;
        lastProgressAt = Time.time;
        Save();
    }

    private void Update()
    {
        if (result.status != "in_progress") return;
        if (Time.time - startedAt > 45f) { Finish("failed", "total_route_timeout"); return; }

        var target = targets[targetIndex];
        var current = transform.position;
        var horizontal = new Vector3(target.x - current.x, 0f, target.z - current.z);
        var distance = horizontal.magnitude;
        if (distance < bestDistance - 0.025f) {
            bestDistance = distance;
            lastProgressAt = Time.time;
        }
        if (distance < 0.16f && Mathf.Abs(current.y - target.y) < 0.28f && controller.isGrounded) {
            result.checkpoints[targetIndex] = new Checkpoint {
                name = names[targetIndex], x = current.x, y = current.y, z = current.z,
                elapsed_seconds = Time.time - startedAt
            };
            Save();
            targetIndex++;
            if (targetIndex == targets.Length) { Finish("pass", "continuous_character_controller_route"); return; }
            bestDistance = float.PositiveInfinity;
            lastProgressAt = Time.time;
            return;
        }
        if (Time.time - lastProgressAt > 5f) {
            Finish("failed", "stalled_at_" + names[targetIndex]);
            return;
        }
        if (controller.isGrounded && verticalSpeed < 0f) verticalSpeed = -1f;
        else verticalSpeed += Physics.gravity.y * Time.deltaTime;
        var speed = 1.6f;
        var movement = horizontal.normalized * Mathf.Min(speed * Time.deltaTime, distance);
        movement.y = verticalSpeed * Time.deltaTime;
        var flags = controller.Move(movement);
        if ((flags & CollisionFlags.Below) != 0) result.grounded_frames++;
        if ((flags & CollisionFlags.Sides) != 0) result.side_collision_frames++;
    }

    private void OnDisable()
    {
        if (result != null && result.status == "in_progress") Finish("interrupted", "play_mode_stopped");
    }

    private void OnGUI()
    {
        if (result == null) return;
        GUI.Box(new Rect(16f, 16f, 460f, 62f),
            "WorldBuilder walk: " + result.status + "\n" +
            "Checkpoint " + Mathf.Min(targetIndex, targets.Length) + "/" + targets.Length +
            "  Feet: " + transform.position.ToString("F2"));
    }

    private void Finish(string status, string reason)
    {
        result.status = status;
        result.reason = reason;
        Save();
        if (status == "pass") {
            var camera = GetComponentInChildren<Camera>();
            if (camera != null) camera.transform.LookAt(new Vector3(17f, 3.6f, 11f));
            StartCoroutine(CaptureResult());
        }
        Debug.Log("WorldBuilder walk validation: " + status + " (" + reason + ") at " + transform.position);
    }

    private IEnumerator CaptureResult()
    {
        yield return new WaitForEndOfFrame();
        var image = ScreenCapture.CaptureScreenshotAsTexture();
        if (image == null) {
            Debug.LogWarning("WorldBuilder walk screenshot capture returned no image");
            yield break;
        }
        var path = Path.ChangeExtension(outputPath, ".png");
        File.WriteAllBytes(path, image.EncodeToPNG());
        Destroy(image);
        result.screenshot = Path.GetFileName(path);
        Save();
        Debug.Log("WorldBuilder walk screenshot saved: " + path);
    }

    private void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));
        File.WriteAllText(outputPath, JsonUtility.ToJson(result, true));
    }
}
