using System;
using System.Collections;
using System.IO;
using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public sealed class WorldBuilderCityBridgeWalkValidator : MonoBehaviour
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
        public string source_world_id;
        public string source_revision_id;
        public string scene;
        public string status;
        public string reason;
        public int grounded_frames;
        public int bridge_grounded_frames;
        public int side_collision_frames;
        public float player_height;
        public float player_radius;
        public string screenshot;
        public Checkpoint[] checkpoints;
    }

    public string sourceWorldId;
    public string sourceRevisionId;

    private readonly Vector3[] targets = {
        new Vector3(248f, 2f, 271f),
        new Vector3(256f, 2f, 271f),
        new Vector3(268f, 2f, 271f)
    };
    private readonly string[] names = { "west_road", "bridge_center", "east_road" };
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
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_WALK_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            outputPath = Path.GetFullPath(Path.Combine(Application.dataPath,
                gameObject.scene.name == "CityChunkBridgeWalk"
                    ? "../../../../artifacts/unity-city/v3-seam-walk-validation.json"
                    : "../../../../artifacts/unity-city/bridge-walk-validation.json"));
        result = new Result {
            unity_version = Application.unityVersion,
            source_world_id = sourceWorldId,
            source_revision_id = sourceRevisionId,
            scene = gameObject.scene.name,
            status = "in_progress",
            reason = "",
            player_height = controller.height,
            player_radius = controller.radius,
            checkpoints = new Checkpoint[targets.Length]
        };
        startedAt = Time.time;
        lastProgressAt = Time.time;
        Save();
    }

    private void Update()
    {
        if (result.status != "in_progress") return;
        if (Time.time - startedAt > 35f) { Finish("failed", "total_route_timeout"); return; }

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
            if (targetIndex == targets.Length) {
                if (result.grounded_frames < 30 || result.bridge_grounded_frames < 5)
                    Finish("failed", "insufficient_grounded_bridge_frames");
                else Finish("pass", "continuous_character_controller_bridge_route");
                return;
            }
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
        var movement = horizontal.normalized * Mathf.Min(2.4f * Time.deltaTime, distance);
        movement.y = verticalSpeed * Time.deltaTime;
        var flags = controller.Move(movement);
        if ((flags & CollisionFlags.Below) != 0) {
            result.grounded_frames++;
            if (transform.position.x >= 252.25f && transform.position.x <= 259.75f)
                result.bridge_grounded_frames++;
        }
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
            "WorldBuilder city bridge: " + result.status + "\n" +
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
            if (camera != null) camera.transform.LookAt(new Vector3(256f, 2f, 271f));
            StartCoroutine(CaptureResult());
        }
        Debug.Log("WorldBuilder city bridge walk: " + status + " (" + reason + ") at " + transform.position);
    }

    private IEnumerator CaptureResult()
    {
        yield return new WaitForEndOfFrame();
        var image = ScreenCapture.CaptureScreenshotAsTexture();
        if (image == null) yield break;
        var path = Path.ChangeExtension(outputPath, ".png");
        File.WriteAllBytes(path, image.EncodeToPNG());
        Destroy(image);
        result.screenshot = Path.GetFileName(path);
        Save();
    }

    private void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));
        File.WriteAllText(outputPath, JsonUtility.ToJson(result, true));
    }
}
