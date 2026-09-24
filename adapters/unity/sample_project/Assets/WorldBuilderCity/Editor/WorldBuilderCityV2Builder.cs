using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class WorldBuilderCityV2Builder
{
    [Serializable] private sealed class Piece { public string name; public string source_id; }
    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
        public string adapter_version;
        public string unity_version;
        public Piece[] pieces;
    }
    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string target_load = "failed";
        public string collision = "not_run";
        public string door_orientation = "not_run";
        public string stair_mapping = "not_run";
        public string scene_path;
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderCity/v2/";

    [MenuItem("World Builder/Build City Interiors v2")]
    public static void BuildInteriors()
    {
        var result = new Result { unity_version = Application.unityVersion,
            scene_path = Base + "CityInteriors.unity" };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + "city.glb");
            if (prefab == null) throw new InvalidOperationException("glTFast did not import city v2 GLB");
            var manifest = ReadManifest();
            if (manifest.adapter_version != "0.1.0-city.2" || manifest.unity_version != Application.unityVersion)
                throw new InvalidOperationException("city v2 manifest or Unity profile mismatch");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;
            result.expected_pieces = manifest.pieces.Length;
            if (result.expected_pieces < 100) throw new InvalidOperationException("city v2 manifest is incomplete");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = UnityEngine.Object.Instantiate(prefab);
            root.name = manifest.source_world_id;
            var found = new HashSet<string>();
            foreach (var piece in manifest.pieces)
            {
                if (!found.Add(piece.name)) throw new InvalidOperationException("duplicate piece: " + piece.name);
                var part = Find(root.transform, piece.name);
                if (part == null) throw new InvalidOperationException("missing imported piece: " + piece.name);
                part.gameObject.AddComponent<WorldBuilderSourceId>().sourceId = piece.source_id;
                var meshes = part.GetComponentsInChildren<MeshFilter>(true);
                if (meshes.Length != 1 || meshes[0].sharedMesh == null)
                    throw new InvalidOperationException("expected one mesh: " + piece.name);
                meshes[0].gameObject.AddComponent<MeshCollider>().sharedMesh = meshes[0].sharedMesh;
                result.mapped_pieces++;
                result.mesh_colliders++;
            }
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";

            var door = Find(root.transform, "building_000_east_door_lintel");
            if (door == null) throw new InvalidOperationException("first interior door lintel missing");
            var bounds = door.GetComponentInChildren<Renderer>().bounds;
            if (!Near(bounds.min.x, 31.8f) || !Near(bounds.max.x, 32f) ||
                !Near(bounds.min.y, 4.6f) || !Near(bounds.max.y, 8f) ||
                !Near(bounds.min.z, 16f) || !Near(bounds.max.z, 18f))
                throw new InvalidOperationException("city interior door orientation changed: " + bounds);
            result.door_orientation = "pass";
            for (var building = 0; building < 5; building++)
                for (var step = 1; step <= 20; step++)
                    if (Find(root.transform, $"stair_{building:000}_tread_{step:00}") == null)
                        throw new InvalidOperationException("missing stair tread " + building + "/" + step);
            result.stair_mapping = "pass";

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
            var camera = new GameObject("Overview Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(24f, 17f, 3f);
            camera.transform.LookAt(new Vector3(24f, 5f, 22f));
            camera.clearFlags = CameraClearFlags.Skybox;
            EditorSceneManager.SaveScene(scene, result.scene_path);
            AssetDatabase.SaveAssets();
            result.target_load = "pass";
            Debug.Log("WorldBuilder city v2 imported: " + result.mapped_pieces + " pieces, " +
                      result.mesh_colliders + " colliders, revision " + result.source_revision_id);
        }
        catch (Exception exception)
        {
            result.error = exception.ToString();
            Debug.LogException(exception);
            WriteResult(result);
            throw;
        }
        WriteResult(result);
    }

    [MenuItem("World Builder/Build City Interior Walk Validation")]
    public static void BuildInteriorWalkValidation()
    {
        BuildInteriors();
        CreateWalkScene(0);
    }

    [MenuItem("World Builder/Build Remaining City Interior Walk Validations")]
    public static void BuildRemainingInteriorWalkValidations()
    {
        BuildInteriors();
        for (var building = 1; building < 5; building++)
        {
            EditorSceneManager.OpenScene(Base + "CityInteriors.unity", OpenSceneMode.Single);
            CreateWalkScene(building);
        }
    }

    private static void CreateWalkScene(int buildingIndex)
    {
        var manifest = ReadManifest();
        var eastOffset = 44f * buildingIndex;
        var player = new GameObject($"Interior validation player {buildingIndex:000}");
        player.transform.position = new Vector3(34f + eastOffset, 2.1f, 16.5f);
        var controller = player.AddComponent<CharacterController>();
        controller.height = 1.8f;
        controller.radius = 0.25f;
        controller.center = new Vector3(0f, 0.9f, 0f);
        controller.stepOffset = 0.45f;
        controller.slopeLimit = 60f;
        var validator = player.AddComponent<WorldBuilderCityInteriorWalkValidator>();
        validator.sourceWorldId = manifest.source_world_id;
        validator.sourceRevisionId = manifest.source_revision_id;
        validator.buildingIndex = buildingIndex;

        var camera = new GameObject("Interior first-person camera").AddComponent<Camera>();
        camera.transform.SetParent(player.transform, false);
        camera.transform.localPosition = new Vector3(0f, 1.6f, 0f);
        camera.transform.localRotation = Quaternion.Euler(0f, -90f, 0f);
        camera.tag = "MainCamera";
        camera.clearFlags = CameraClearFlags.Skybox;
        var overview = GameObject.Find("Overview Camera");
        if (overview != null) overview.GetComponent<Camera>().enabled = false;

        var path = Base + (buildingIndex == 0 ? "CityInteriorWalk.unity" :
            $"CityInteriorWalk{buildingIndex:000}.unity");
        EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), path);
        Debug.Log("WorldBuilder city interior walk scene saved: " + path);
    }

    private static Manifest ReadManifest()
    {
        var path = Path.Combine(Application.dataPath, "WorldBuilderCity", "v2", "manifest.json");
        var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(path));
        if (manifest == null || manifest.pieces == null || manifest.pieces.Length == 0)
            throw new InvalidOperationException("city v2 manifest has no pieces");
        return manifest;
    }

    private static bool Near(float actual, float expected) => Math.Abs(actual - expected) <= 0.02f;

    private static Transform Find(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform child in root)
        {
            var match = Find(child, name);
            if (match != null) return match;
        }
        return null;
    }

    private static void WriteResult(Result result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V2_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v2-target-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
