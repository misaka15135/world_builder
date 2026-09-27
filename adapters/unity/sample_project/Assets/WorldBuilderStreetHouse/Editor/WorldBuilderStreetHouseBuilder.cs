using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class WorldBuilderStreetHouseBuilder
{
    [Serializable] private sealed class Piece
    {
        public string name;
        public string source_id;
    }

    [Serializable] private sealed class Manifest
    {
        public string version;
        public string source_id;
        public string geometry_sha256;
        public string unity_version;
        public int piece_count;
        public Piece[] pieces;
    }

    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string version;
        public string source_id;
        public string geometry_sha256;
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public string scene_path;
        public string target_load = "failed";
        public string collision = "not_run";
        public string error;
    }

    private const string Base = "Assets/WorldBuilderStreetHouse/";
    private const string ScenePath = Base + "StreetHouse.unity";

    [MenuItem("World Builder/Build Street House Walk")]
    public static void BuildWalk()
    {
        var manifest = ReadManifest();
        CheckManifest(manifest);
        EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        var player = new GameObject("Street House Walker");
        player.transform.position = new Vector3(8.5f, 1.9f, 0.5f);
        var controller = player.AddComponent<CharacterController>();
        controller.height = 1.8f;
        controller.radius = .25f;
        controller.stepOffset = .6f;
        controller.skinWidth = .04f;
        var validator = player.AddComponent<WorldBuilderStreetHouseWalkValidator>();
        validator.sourceId = manifest.source_id;
        validator.geometryHash = manifest.geometry_sha256;
        EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), Base + "StreetHouseWalk.unity");
        Debug.Log("WorldBuilder street house walk scene saved");
    }

    [MenuItem("World Builder/Run Street House Walk")]
    public static void RunWalk()
    {
        EditorSceneManager.OpenScene(Base + "StreetHouseWalk.unity", OpenSceneMode.Single);
        EditorApplication.isPlaying = true;
    }

    [MenuItem("World Builder/Build Street House Study")]
    public static void Build()
    {
        var result = new Result { unity_version = Application.unityVersion, scene_path = ScenePath };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var manifest = ReadManifest();
            CheckManifest(manifest);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + "street_house.glb");
            if (prefab == null) throw new InvalidOperationException("glTFast did not import street_house.glb");
            CopyIdentity(result, manifest);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = UnityEngine.Object.Instantiate(prefab);
            root.name = manifest.source_id;
            var seen = new HashSet<string>();
            foreach (var piece in manifest.pieces)
            {
                if (!seen.Add(piece.name)) throw new InvalidOperationException("duplicate piece " + piece.name);
                var part = Find(root.transform, piece.name);
                if (part == null) throw new InvalidOperationException("missing GLB node " + piece.name);
                part.gameObject.AddComponent<WorldBuilderSourceId>().sourceId = piece.source_id;
                var meshes = part.GetComponentsInChildren<MeshFilter>(true);
                if (meshes.Length != 1 || meshes[0].sharedMesh == null)
                    throw new InvalidOperationException("expected one mesh on " + piece.name);
                meshes[0].gameObject.AddComponent<MeshCollider>().sharedMesh = meshes[0].sharedMesh;
                result.mapped_pieces++;
                result.mesh_colliders++;
            }
            var light = new GameObject("Study Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.35f;
            light.transform.rotation = Quaternion.Euler(45f, -30f, 0f);
            var camera = new GameObject("Street View Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(10f, 8f, -18f);
            camera.transform.rotation = Quaternion.LookRotation(new Vector3(10f, 5f, 8f) - camera.transform.position);
            camera.fieldOfView = 48f;
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            result.target_load = "pass";
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";
            Debug.Log("WorldBuilder street house imported: " + result.mapped_pieces);
        }
        catch (Exception error)
        {
            result.error = error.ToString();
            Debug.LogException(error);
            WriteResult(result);
            throw;
        }
        WriteResult(result);
    }

    [MenuItem("World Builder/Validate Saved Street House Study")]
    public static void ValidateSaved()
    {
        var result = new Result { unity_version = Application.unityVersion, scene_path = ScenePath };
        try
        {
            var manifest = ReadManifest();
            CheckManifest(manifest);
            CopyIdentity(result, manifest);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var root = GameObject.Find(manifest.source_id);
            if (root == null) throw new InvalidOperationException("source root missing from saved scene");
            foreach (var piece in manifest.pieces)
            {
                var part = Find(root.transform, piece.name);
                if (part == null || part.GetComponent<WorldBuilderSourceId>()?.sourceId != piece.source_id)
                    throw new InvalidOperationException("source mapping mismatch " + piece.name);
                if (part.GetComponentInChildren<MeshCollider>() == null)
                    throw new InvalidOperationException("mesh collider missing " + piece.name);
                result.mapped_pieces++;
                result.mesh_colliders++;
            }
            result.target_load = "pass";
            result.collision = "pass";
            Debug.Log("WorldBuilder saved street house verified: " + result.mapped_pieces);
        }
        catch (Exception error)
        {
            result.error = error.ToString();
            Debug.LogException(error);
            WriteResult(result);
            throw;
        }
        WriteResult(result);
    }

    [MenuItem("World Builder/Capture Street House Study")]
    public static void CaptureView()
    {
        EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
        var camera = GameObject.Find("Street View Camera")?.GetComponent<Camera>();
        if (camera == null) throw new InvalidOperationException("study camera missing");
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_STREET_HOUSE_IMAGE");
        if (string.IsNullOrEmpty(path)) throw new InvalidOperationException("image path is required");
        if (Environment.GetEnvironmentVariable("WORLD_BUILDER_STREET_HOUSE_VIEW") == "oblique")
        {
            camera.transform.position = new Vector3(28f, 10f, -19f);
            camera.transform.rotation = Quaternion.LookRotation(
                new Vector3(10f, 5f, 8f) - camera.transform.position);
        }
        var target = new RenderTexture(1280, 720, 24, RenderTextureFormat.ARGB32);
        var old = RenderTexture.active;
        try
        {
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            var pixels = new Texture2D(1280, 720, TextureFormat.RGB24, false);
            pixels.ReadPixels(new Rect(0, 0, 1280, 720), 0, 0);
            pixels.Apply();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, pixels.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(pixels);
            Debug.Log("WorldBuilder street house image saved: " + path);
        }
        finally
        {
            camera.targetTexture = null;
            RenderTexture.active = old;
            UnityEngine.Object.DestroyImmediate(target);
        }
    }

    private static Manifest ReadManifest()
    {
        return JsonUtility.FromJson<Manifest>(File.ReadAllText(
            Path.Combine(Application.dataPath, "WorldBuilderStreetHouse", "manifest.json")));
    }

    private static void CheckManifest(Manifest manifest)
    {
        if (manifest == null || manifest.pieces == null || manifest.pieces.Length == 0 ||
            manifest.piece_count != manifest.pieces.Length || manifest.unity_version != Application.unityVersion)
            throw new InvalidOperationException("study manifest or Unity version invalid");
    }

    private static void CopyIdentity(Result result, Manifest manifest)
    {
        result.version = manifest.version;
        result.source_id = manifest.source_id;
        result.geometry_sha256 = manifest.geometry_sha256;
        result.expected_pieces = manifest.piece_count;
    }

    private static Transform Find(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform child in root)
        {
            var found = Find(child, name);
            if (found != null) return found;
        }
        return null;
    }

    private static void WriteResult(Result result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_STREET_HOUSE_RESULT");
        if (string.IsNullOrEmpty(path))
            throw new InvalidOperationException("WORLD_BUILDER_STREET_HOUSE_RESULT is required");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
