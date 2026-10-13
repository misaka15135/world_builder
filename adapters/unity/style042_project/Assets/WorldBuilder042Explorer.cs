using UnityEngine;

/// <summary>Free camera for viewing the delivered scene; not a walking proof.</summary>
public sealed class WorldBuilder042Explorer : MonoBehaviour
{
    void Update()
    {
        if (Input.GetMouseButton(1))
        {
            Vector3 angles=transform.eulerAngles;
            angles.x-=Input.GetAxis("Mouse Y")*2;
            angles.y+=Input.GetAxis("Mouse X")*2;
            transform.eulerAngles=angles;
        }
        float speed=Input.GetKey(KeyCode.LeftShift)?18:7;
        Vector3 v=new Vector3(Input.GetAxisRaw("Horizontal"),
                             (Input.GetKey(KeyCode.E)?1:0)-(Input.GetKey(KeyCode.Q)?1:0),
                             Input.GetAxisRaw("Vertical"));
        transform.Translate(v*speed*Time.deltaTime,Space.Self);
    }
}
