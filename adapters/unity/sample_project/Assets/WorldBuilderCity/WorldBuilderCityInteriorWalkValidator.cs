using System;
using System.Collections;
using System.IO;
using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public sealed class WorldBuilderCityInteriorWalkValidator : MonoBehaviour
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
        public string source_building_id;
        public string scene;
        public string status;
        public string reason;
        public int grounded_frames;
        public int stair_grounded_frames;
        public int side_collision_frames;
        public float player_height;
        public float player_radius;
        public string screenshot;
        public Checkpoint[] checkpoints;
    }

    public string sourceWorldId;
    public string sourceRevisionId;
    public int buildingIndex;

    private readonly Vector3[] targets = {
        new Vector3(33f, 2f, 16.5f),
        new Vector3(31f, 2.2f, 16.5f),
        new Vector3(28f, 2.2f, 17.1f),
        new Vector3(28f, 5.2f, 26f),
        new Vector3(25.5f, 5.2f, 26f)
    };
    private readonly string[] names = {
        "access_road", "through_east_door", "stair_foot", "upper_landing", "upper_room"
    };
    private CharacterController controller;
    private Result result;
    private int targetIndex;
    private float verticalSpeed;
    private float startedAt;
    private float lastProgressAt;
    private float bestDistance = float.PositiveInfinity;
    private string outputPath;
    private float eastOffset;

    private void Start()
    {
        controller = GetComponent<CharacterController>();
        eastOffset = 44f * buildingIndex;
        outputPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_INTERIOR_WALK_VALIDATION");
        if (string.IsNullOrEmpty(outputPath))
            outputPath = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/" + (buildingIndex == 0 ?
                "interior-walk-validation.json" : $"interior-walk-building-{buildingIndex:000}.json")));
        result = new Result {
            unity_version = Application.unityVersion,
            source_world_id = sourceWorldId,
            source_revision_id = sourceRevisionId,
            source_building_id = $"building_{buildingIndex:000}",
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
        if (Time.time - startedAt > 50f) { Finish("failed", "total_route_timeout"); return; }

        var target = targets[targetIndex] + new Vector3(eastOffset, 0f, 0f);
        var current = transform.position;
        var horizontal = new Vector3(target.x - current.x, 0f, target.z - current.z);
        var distance = horizontal.magnitude;
        if (distance < bestDistance - 0.025f) {
            bestDistance = distance;
            lastProgressAt = Time.time;
        }
        if (distance < 0.17f && Mathf.Abs(current.y - target.y) < 0.3f && controller.isGrounded) {
            result.checkpoints[targetIndex] = new Checkpoint {
                name = names[targetIndex], x = current.x, y = current.y, z = current.z,
                elapsed_seconds = Time.time - startedAt
            };
            Save();
            targetIndex++;
            if (targetIndex == targets.Length) {
                if (result.grounded_frames < 30 || result.stair_grounded_frames < 20)
                    Finish("failed", "insufficient_grounded_stair_frames");
                else Finish("pass", "continuous_door_stair_upper_room_route");
                return;
            }
            bestDistance = float.PositiveInfinity;
            lastProgressAt = Time.time;
            return;
        }
        if (Time.time - lastProgressAt > 6f) {
            Finish("failed", "stalled_at_" + names[targetIndex]);
            return;
        }
        if (controller.isGrounded && verticalSpeed < 0f) verticalSpeed = -1f;
        else verticalSpeed += Physics.gravity.y * Time.deltaTime;
        var movement = horizontal.normalized * Mathf.Min(1.5f * Time.deltaTime, distance);
        movement.y = verticalSpeed * Time.deltaTime;
        var flags = controller.Move(movement);
        if ((flags & CollisionFlags.Below) != 0) {
            result.grounded_frames++;
            if (transform.position.x >= 27.2f + eastOffset && transform.position.x <= 28.8f + eastOffset &&
                transform.position.z >= 17f && transform.position.z <= 27f &&
                transform.position.y >= 2.2f && transform.position.y <= 5.35f)
                result.stair_grounded_frames++;
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
            "WorldBuilder city interior " + result.source_building_id + ": " + result.status + "\n" +
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
            if (camera != null) camera.transform.LookAt(new Vector3(28f + eastOffset, 3.6f, 21f));
            StartCoroutine(CaptureResult());
        }
        Debug.Log("WorldBuilder city interior walk: " + status + " (" + reason + ") at " + transform.position);
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
