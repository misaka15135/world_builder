using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class WorldBuilderCityBuilder
{
    [Serializable] private sealed class Piece { public string name; public string source_id; }
    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
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
        public string orientation = "not_run";
        public string scene_path;
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderCity/";

    [MenuItem("World Builder/Build City Static")]
    public static void Build()
    {
        var result = new Result { unity_version = Application.unityVersion,
            scene_path = Base + "CityStatic.unity" };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + "city.glb");
            if (prefab == null) throw new InvalidOperationException("glTFast did not import city.glb");
            var manifestPath = Path.Combine(Application.dataPath, "WorldBuilderCity", "manifest.json");
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(manifestPath));
            if (manifest == null || manifest.pieces == null || manifest.pieces.Length == 0)
                throw new InvalidOperationException("city manifest has no pieces");
            if (manifest.unity_version != Application.unityVersion)
                throw new InvalidOperationException("Unity version differs from export profile");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;
            result.expected_pieces = manifest.pieces.Length;

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = UnityEngine.Object.Instantiate(prefab);
            root.name = manifest.source_world_id;
            var found = new HashSet<string>();
            foreach (var piece in manifest.pieces)
            {
                if (!found.Add(piece.name)) throw new InvalidOperationException("duplicate piece: " + piece.name);
                var part = Find(root.transform, piece.name);
                if (part == null) throw new InvalidOperationException("missing GLB node: " + piece.name);
                part.gameObject.AddComponent<WorldBuilderSourceId>().sourceId = piece.source_id;
                var meshes = part.GetComponentsInChildren<MeshFilter>(true);
                if (meshes.Length != 1 || meshes[0].sharedMesh == null)
                    throw new InvalidOperationException("expected one mesh per piece: " + piece.name);
                meshes[0].gameObject.AddComponent<MeshCollider>().sharedMesh = meshes[0].sharedMesh;
                result.mapped_pieces++;
                result.mesh_colliders++;
            }
            var bridge = Find(root.transform, "bridge_main");
            if (bridge == null) throw new InvalidOperationException("bridge_main missing");
            var bounds = bridge.GetComponentInChildren<Renderer>().bounds;
            if (!Near(bounds.min.x, 252f) || !Near(bounds.max.x, 260f) ||
                !Near(bounds.min.y, 1.6f) || !Near(bounds.max.y, 2f) ||
                !Near(bounds.min.z, 268f) || !Near(bounds.max.z, 274f))
                throw new InvalidOperationException("bridge orientation or scale changed: " + bounds);
            result.orientation = "pass";
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
            var camera = new GameObject("Overview Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(256f, 250f, 5f);
            camera.transform.LookAt(new Vector3(256f, 0f, 256f));
            camera.clearFlags = CameraClearFlags.Skybox;
            EditorSceneManager.SaveScene(scene, result.scene_path);
            AssetDatabase.SaveAssets();
            result.target_load = "pass";
            Debug.Log("WorldBuilder city imported: " + result.mapped_pieces + " pieces, " +
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
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../../artifacts/unity-city/target-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
