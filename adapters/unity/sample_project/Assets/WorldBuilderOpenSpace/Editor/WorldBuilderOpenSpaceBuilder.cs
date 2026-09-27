using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class WorldBuilderOpenSpaceBuilder
{
    [Serializable] private sealed class Piece
    {
        public string name;
        public string source_id;
    }

    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
        public string source_id;
        public string unity_version;
        public int piece_count;
        public Piece[] pieces;
    }

    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string source_id;
        public string target_load = "failed";
        public string collision = "not_run";
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public string scene_path;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderOpenSpace/";

    [MenuItem("World Builder/Build Open Space Walk")]
    public static void BuildWalk()
    {
        EditorSceneManager.OpenScene(Base + "OpenSpacePlaza.unity", OpenSceneMode.Single);
        var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(
            Path.Combine(Application.dataPath, "WorldBuilderOpenSpace", "manifest.json")));
        if (manifest == null || manifest.source_id != "open_space_site_001")
            throw new InvalidOperationException("walk scene source manifest mismatch");
        var path = GameObject.Find(manifest.source_id + "_path");
        if (path == null || path.GetComponentInChildren<MeshCollider>() == null)
            throw new InvalidOperationException("walk path source collider missing");
        var player = new GameObject("Open space path walker");
        player.transform.position = new Vector3(308.811f, 1.3f, 207.5f);
        var controller = player.AddComponent<CharacterController>();
        controller.height = 1.8f;
        controller.radius = 0.25f;
        controller.skinWidth = 0.04f;
        var validator = player.AddComponent<WorldBuilderOpenSpaceWalkValidator>();
        validator.sourceWorldId = manifest.source_world_id;
        validator.sourceRevisionId = manifest.source_revision_id;
        validator.sourceId = manifest.source_id;
        var scenePath = Base + "OpenSpacePlazaWalk.unity";
        EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), scenePath);
        Debug.Log("WorldBuilder open space walk scene saved: " + scenePath);
    }

    [MenuItem("World Builder/Run Open Space Walk")]
    public static void RunWalk()
    {
        EditorSceneManager.OpenScene(Base + "OpenSpacePlazaWalk.unity", OpenSceneMode.Single);
        EditorApplication.isPlaying = true;
    }

    [MenuItem("World Builder/Validate Saved Open Space Sample")]
    public static void ValidateSaved()
    {
        var result = new Result { unity_version = Application.unityVersion,
            scene_path = Base + "OpenSpacePlaza.unity" };
        try
        {
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(
                Path.Combine(Application.dataPath, "WorldBuilderOpenSpace", "manifest.json")));
            if (manifest == null || manifest.pieces == null || manifest.unity_version != Application.unityVersion)
                throw new InvalidOperationException("saved scene manifest or Unity version is invalid");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;
            result.source_id = manifest.source_id;
            result.expected_pieces = manifest.pieces.Length;
            EditorSceneManager.OpenScene(result.scene_path, OpenSceneMode.Single);
            var root = GameObject.Find(manifest.source_world_id);
            if (root == null) throw new InvalidOperationException("saved scene has no source world root");
            foreach (var piece in manifest.pieces)
            {
                var part = Find(root.transform, piece.name);
                if (part == null) throw new InvalidOperationException("saved node missing " + piece.name);
                var source = part.GetComponent<WorldBuilderSourceId>();
                if (source == null || source.sourceId != piece.source_id)
                    throw new InvalidOperationException("saved source ID mismatch " + piece.name);
                if (part.GetComponentInChildren<MeshCollider>() == null)
                    throw new InvalidOperationException("saved collider missing " + piece.name);
                result.mapped_pieces++;
                result.mesh_colliders++;
            }
            result.target_load = "pass";
            result.collision = "pass";
            Debug.Log("WorldBuilder saved open space verified: " + result.mapped_pieces);
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

    [MenuItem("World Builder/Build Open Space Sample")]
    public static void Build()
    {
        var result = new Result {
            unity_version = Application.unityVersion,
            scene_path = Base + "OpenSpacePlaza.unity"
        };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + "open_space.glb");
            if (prefab == null) throw new InvalidOperationException("glTFast did not import open_space.glb");
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(
                Path.Combine(Application.dataPath, "WorldBuilderOpenSpace", "manifest.json")));
            if (manifest == null || manifest.pieces == null || manifest.pieces.Length == 0)
                throw new InvalidOperationException("open-space manifest has no pieces");
            if (manifest.unity_version != Application.unityVersion)
                throw new InvalidOperationException("Unity version differs from export profile");
            if (manifest.piece_count != manifest.pieces.Length)
                throw new InvalidOperationException("manifest piece count differs from list");

            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;
            result.source_id = manifest.source_id;
            result.expected_pieces = manifest.pieces.Length;

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var root = UnityEngine.Object.Instantiate(prefab);
            root.name = manifest.source_world_id;
            var names = new HashSet<string>();
            foreach (var piece in manifest.pieces)
            {
                if (!names.Add(piece.name)) throw new InvalidOperationException("duplicate piece " + piece.name);
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

            var paving = Find(root.transform, manifest.source_id + "_paving");
            var path = Find(root.transform, manifest.source_id + "_path");
            if (paving == null || path == null)
                throw new InvalidOperationException("source paving or path missing");
            var bounds = paving.GetComponentInChildren<Renderer>().bounds;
            if (bounds.size.x < 2f || bounds.size.z < 2f || Math.Abs(bounds.min.y) > 0.02f)
                throw new InvalidOperationException("paving scale or up-axis changed: " + bounds);
            var pathBounds = path.GetComponentInChildren<Renderer>().bounds;
            if (pathBounds.min.y < bounds.max.y - 0.02f)
                throw new InvalidOperationException("path fell below paving");

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
            var camera = new GameObject("Overview Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(bounds.center.x, 70f, bounds.center.z);
            camera.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            camera.orthographic = true;
            camera.orthographicSize = Mathf.Max(bounds.size.x, bounds.size.z) * 0.7f;
            EditorSceneManager.SaveScene(scene, result.scene_path);
            AssetDatabase.SaveAssets();

            result.target_load = "pass";
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";
            Debug.Log("WorldBuilder open space imported: " + result.mapped_pieces +
                      " pieces, revision " + result.source_revision_id);
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
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_OPEN_SPACE_VALIDATION");
        if (string.IsNullOrEmpty(path))
            throw new InvalidOperationException("WORLD_BUILDER_UNITY_OPEN_SPACE_VALIDATION is required");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
