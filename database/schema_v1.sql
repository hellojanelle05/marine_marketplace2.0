BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "order" (
	"id"	INTEGER,
	"product_id"	INTEGER,
	"product_name"	TEXT,
	"vendor_name"	TEXT,
	"buyer_id"	INTEGER,
	"quantity"	INTEGER,
	"price_each"	REAL,
	"status"	TEXT,
	"created_at"	TEXT,
	PRIMARY KEY("id")
);
CREATE TABLE IF NOT EXISTS "product" (
	"id"	INTEGER,
	"name"	TEXT,
	"price"	REAL,
	"quantity"	INTEGER,
	"description"	TEXT,
	"image_path"	TEXT,
	"vendor_id"	INTEGER,
	"created_at"	TEXT,
	PRIMARY KEY("id")
);
CREATE TABLE IF NOT EXISTS "user" (
	"id"	INTEGER,
	"username"	TEXT UNIQUE,
	"password"	TEXT,
	"fullname"	TEXT,
	"role"	TEXT,
	"created_at"	TEXT,
	PRIMARY KEY("id")
);
INSERT INTO "order" VALUES (1,1,'Bangus','Vendor One',3,2,180.0,'Pending','2025-11-04T16:24:25.797987');
INSERT INTO "order" VALUES (2,1,'Bangus','Vendor One',3,1,180.0,'Delivered','2025-11-04T16:24:25.797999');
INSERT INTO "order" VALUES (3,5,'Crab','Vendor One',3,1,420.0,'Pending','2025-11-04 17:28:59.647782');
INSERT INTO "product" VALUES (1,'Bangus',180.0,20,'Fresh bangus from local farms','uploads/bangus.jpg',2,'2025-11-04T16:24:25.795503');
INSERT INTO "product" VALUES (2,'Tilapia',140.0,10,'Locally caught tilapia','uploads/tilapia.jpg',2,'2025-11-04T16:24:25.795520');
INSERT INTO "product" VALUES (3,'Galunggong',120.0,25,'Small pelagic fish','uploads/galunggong.jpg',2,'2025-11-04T16:24:25.795525');
INSERT INTO "product" VALUES (4,'Shrimp',350.0,5,'Fresh shrimp packs','uploads/shrimp.jpg',2,'2025-11-04T16:24:25.795530');
INSERT INTO "product" VALUES (5,'Crab',420.0,2,'Fresh crab per kg','uploads/crab.jpg',2,'2025-11-04T16:24:25.795535');
INSERT INTO "user" VALUES (1,'admin@marine.com','scrypt:32768:8:1$06nDhIukQQp12Tul$3a07a9d85f77162dcd8ff96d9b3781fcfba05d264abb1bd6446b1f03ea5b9498ae22853baf9ec529707337631adce939b2aff9d09fed5dd762ce5d90820f8371','Admin Marine','admin','2025-11-04T16:24:24.933418');
INSERT INTO "user" VALUES (2,'vendor@marine.com','scrypt:32768:8:1$Gvp9Pe53AwkQycbx$8906086eb49dd92b9600081f3765254097736c501a09049576d1823d789b23446e483f366eb2f661fd1c45a128d6b7180acbccd2f26d1f84fd296a28075e0c90','Vendor One','vendor','2025-11-04T16:24:25.395886');
INSERT INTO "user" VALUES (3,'consumer@marine.com','scrypt:32768:8:1$8i2Vho1E0V0jcXO2$4663e88dbe5ca3d2a4e0f0e453cd1cc51eb2fb23913238b98b6bf71d40d191fc70884af66a76a8273eab47bf04ae1e10bc4e6b9697636eb81059373345af391f','Janelle','consumer','2025-11-04T16:24:25.792200');
COMMIT;
