using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class WorldBuilderSampleBuilder
{
    [Serializable] private sealed class Piece { public string name; public string source_id; }
    [Serializable] private sealed class Manifest { public Piece[] pieces; }
    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string target_load;
        public string collision;
        public string orientation;
        public string scene_path;
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderSample/";

    [MenuItem("World Builder/Build Library Sample")]
    public static void Build()
    {
        var result = new Result { unity_version = Application.unityVersion,
            target_load = "failed", collision = "not_run", orientation = "not_run",
            scene_path = Base + "LibrarySample.unity", expected_pieces = 26 };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + "library.glb");
            if (prefab == null) throw new InvalidOperationException("glTFast did not import library.glb as a prefab");
            var manifestPath = Path.Combine(Application.dataPath, "WorldBuilderSample", "manifest.json");
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(manifestPath));
            if (manifest?.pieces == null || manifest.pieces.Length != result.expected_pieces)
                throw new InvalidOperationException("sample manifest does not list 26 parts");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = UnityEngine.Object.Instantiate(prefab);
            root.name = "world_two_storey";
            var found = new HashSet<string>();
            foreach (var piece in manifest.pieces)
            {
                if (!found.Add(piece.name)) throw new InvalidOperationException("duplicate piece: " + piece.name);
                var part = Find(root.transform, piece.name);
                if (part == null) throw new InvalidOperationException("missing imported piece: " + piece.name);
                var source = part.gameObject.AddComponent<WorldBuilderSourceId>();
                source.sourceId = piece.source_id;
                result.mapped_pieces++;
                var meshes = part.GetComponentsInChildren<MeshFilter>(true);
                if (meshes.Length != 1 || meshes[0].sharedMesh == null)
                    throw new InvalidOperationException("expected one mesh: " + piece.name);
                var collider = meshes[0].gameObject.AddComponent<MeshCollider>();
                collider.sharedMesh = meshes[0].sharedMesh;
                result.mesh_colliders++;
            }
            var window = Find(root.transform, "east_bay_glass").GetComponentInChildren<Renderer>();
            var bounds = window.bounds;
            if (!Near(bounds.min.x, 23.75f) || !Near(bounds.max.x, 24f) ||
                !Near(bounds.min.y, 5f) || !Near(bounds.max.y, 7f) ||
                !Near(bounds.min.z, 12f) || !Near(bounds.max.z, 14f))
                throw new InvalidOperationException("east bay orientation or scale changed: " + bounds);
            result.orientation = "pass";
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
            var camera = new GameObject("Overview Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(14f, 8f, -12f);
            camera.transform.LookAt(new Vector3(14f, 4f, 11f));
            camera.clearFlags = CameraClearFlags.Skybox;
            EditorSceneManager.SaveScene(scene, result.scene_path);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(result.scene_path, true) };
            AssetDatabase.SaveAssets();
            result.target_load = "pass";
            Debug.Log("WorldBuilder sample imported: " + result.mapped_pieces + " parts, " + result.mesh_colliders + " colliders");
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

    private static void WriteResult(Result result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../../artifacts/unity-sample/target-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
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
}
